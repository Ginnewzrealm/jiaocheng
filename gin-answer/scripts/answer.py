#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-answer 工具脚本：问题类型判定 / 答案卡机检 / 置信度评级 / 汇总 manifest。

规则全部来自 2026-09-06 红阶段基线实测的 8 条真实失败样本：
1. 类型判定零标准        → classify_question 必须输出判定依据
2. 联网来源不落盘        → SKILL.md 纪律（凡被引用必落盘 L7），脚本不管采集
3. 本地出处无法机检      → check_card 校验本地路径存在性
4. 置信度瞎打            → confidence_grade 三级判定条件成文
5. 二手转引混入          → check_independence（同域/聚合转载不算独立）
6. 与资料库冲突无仲裁    → SKILL.md 纪律（本地 L1/L6 优先+标注）
7. 夸大转引靠自觉        → SKILL.md 纪律（倍数宣称回查原始研究）
8. 观察哨从未触发        → build_manifest 显式分级

用法：
    python3 answer.py classify --question "..."
    python3 answer.py validate --card <card.json> [--library <资料库路径>]
    python3 answer.py manifest --dir <answers目录> --topic "..." [--library <资料库路径>]
"""
import argparse
import glob
import json
import os
import re
from urllib.parse import urlparse

# ---------- 规则1：问题类型判定（判定依据必须显式输出） ----------

# 优先级：争议 > 方法 > 事实（争议型有专门横轴流程，宁可高估不可漏判）
# 方法型用正则："怎么(?!样)"防止"怎么样"误命中（红阶段实测："今天天气怎么样"
# 被"怎么"截胡判成方法型）
_TYPE_SIGNALS = [
    ("争议型", ["哪个", "更好", "还是", "要不要", "该不该", "有用么",
                "有没有用", "是不是智商税", "优劣", "之争", "效果好"]),
    ("方法型", [r"如何", r"怎样", r"怎么(?!样)", r"安排", r"计划", r"步骤",
                r"练", r"设置", r"制定"]),
    ("事实型", ["是什么", "区别", "哪些", "有什么", "为什么", "多少"]),
]


def classify_question(q):
    """判定问题类型。返回 {"类型", "判定依据"}——依据必须显式（红样本#1：
    基线靠偷看期望类型才"判对"，真实场景没有标准答案可偷）。"""
    for t, words in _TYPE_SIGNALS:
        hits = []
        for w in words:
            if "(" in w:
                if re.search(w, q):
                    hits.append(w)
            elif w in q:
                hits.append(w)
        if hits:
            return {"类型": t, "判定依据": f"命中{t}信号：{('、'.join(hits))}"}
    return {"类型": "事实型", "判定依据": "未命中争议/方法信号，按最保守档位归事实型"}


# ---------- 规则3：答案卡机检 ----------

_LAYER_PREFIX = re.compile(r"^L[1-7]/")
_LOCAL_SUFFIX = (".md", ".markdown")


def is_local_source(src):
    """来源是本地资料库路径（L1-L7/xx.md 或裸 .md 文件名）。"""
    s = src.get("来源", "")
    return bool(_LAYER_PREFIX.match(s)) or s.endswith(_LOCAL_SUFFIX)


def check_card(card, library=None):
    """机检答案卡出处。返回 errors 列表（空 = 通过）。

    红样本#3：基线卡里本地来源 url 为空串，机器无法验证文件真实性。
    规则：本地来源 → 路径必须存在于资料库；联网来源 → URL 非空。
    """
    errs = []
    for i, src in enumerate(card.get("出处", []), 1):
        name = src.get("来源", f"出处{i}")
        if is_local_source(src):
            if library:
                p = os.path.join(library, src["来源"])
                if not os.path.exists(p):
                    errs.append(f"本地出处不存在：{src['来源']}（{p}）")
        else:
            if not src.get("url"):
                errs.append(f"联网出处缺 URL：{name}")
    for field in ("问题", "类型", "一句话答案", "置信度", "状态"):
        if not card.get(field):
            errs.append(f"卡片缺必填字段：{field}")
    if card.get("类型") and card["类型"] not in ("事实型", "方法型", "争议型"):
        errs.append(f"卡片类型非法：{card['类型']}（必须是 事实型/方法型/争议型，"
                    f"判定须跑 classify 脚本，依据写入卡片）")
    return errs


# ---------- 规则5：独立性检查 ----------

# 聚合转载域：这些内容农场/门户大量转引原创，与任何源组合都不算独立支撑
_AGGREGATORS = ("sohu.com", "163.com", "sina.com.cn", "baijiahao.baidu.com",
                "toutiao.com", "360doc.com")

# 学术宿主：一个域名下挂海量互相独立的文章（pubmed/pmc/arxiv），
# 独立性按文章 ID 判，不按域名（2026-09-06 e2e 实测修正：两篇独立
# 研究只因同挂 pubmed 被误报同域不独立）
_ACADEMIC_HOSTS = ("pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
                   "europepmc.org", "arxiv.org", "doi.org", "sci-hub")


def _domain(url):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _article_key(url):
    """学术文章的唯一键：文章 ID 本身（跨镜像宿主同 ID = 同一文章，
    如 pubmed 与 europepmc 镜像）。非学术 URL 返回 None。"""
    d = _domain(url)
    if d not in _ACADEMIC_HOSTS:
        return None
    m = re.search(r"(\d{5,9}|PMC\d+|10\.\d{4,9}/\S+)", url)
    return m.group(1) if m else None


def check_independence(sources):
    """检出'假独立'来源。返回 warnings 列表。

    红样本#5：基线把 womenshealthmag 对 Wewege 2021 的转引当独立研究引用。
    规则：同域多条 = 一个来源；聚合转载域 = 永远不能充当独立第二源；
    学术宿主例外——按文章 ID 判独立（同 ID 镜像仍算同一来源）。"""
    warns = []
    seen_domains = {}
    seen_articles = {}
    for src in sources:
        url = src.get("url", "")
        if not url:
            continue  # 本地来源按路径算独立性，不参与域名检查
        d = _domain(url)
        if d in _AGGREGATORS:
            warns.append(f"聚合转载源不算独立来源：{src.get('来源')}（{d}），"
                         f"需回溯原始出处")
        key = _article_key(url)
        if key:
            if key in seen_articles:
                warns.append(f"同一文章的多链接不算独立：{seen_articles[key]} 与 "
                             f"{src.get('来源')}（{key}）")
            else:
                seen_articles[key] = src.get("来源")
            continue  # 学术宿主跳过域名级检查
        if d in seen_domains:
            warns.append(f"同域来源不算独立：{seen_domains[d]} 与 {src.get('来源')} "
                         f"同属 {d}")
        else:
            seen_domains[d] = src.get("来源")
    return warns


# ---------- 规则4：置信度三级判定 ----------

def _authoritative_sources(card, library):
    """权威源 = 本地资料库文件（L1/L6 权重最高但 L2-L5 也算数）
    或显式定级 high 的联网来源。"""
    auth = []
    for src in card.get("出处", []):
        if is_local_source(src):
            if library and os.path.exists(os.path.join(library, src["来源"])):
                auth.append(src)
        elif src.get("定级") == "high":
            auth.append(src)
    return auth


def confidence_grade(card, library=None):
    """三级置信度，判定条件成文（红样本#4：基线三张卡全瞎打"高"）。

    高：≥2 个真正独立的权威源 且 无未决争议
    低：权威源为 0（全是 unknown/低质源）
    中：其余情况（单一权威源 / 有争议点 / 权威+普通混合）
    """
    auth = _authoritative_sources(card, library)
    if len(auth) == 0:
        return "低"
    if len(auth) >= 2 and not card.get("争议点"):
        return "高"
    return "中"


# ---------- 规则8：manifest 与观察哨 ----------

def build_manifest(cards, topic, library=None):
    """汇总 answers-manifest.json。观察哨显式分级（红样本#8：基线全程
    没有触发标准，机制形同虚设）。"""
    watchlist = []
    for card in cards:
        reasons = []
        if card.get("置信度") == "低":
            reasons.append("置信度低")
        if card.get("状态") == "待补采":
            reasons.append("待补采")
        for w in check_independence(card.get("出处", [])):
            reasons.append("独立性存疑")
            break
        for r in reasons:
            watchlist.append({"问题": card.get("问题", "?"), "触发原因": r})
    return {
        "topic": topic,
        "cards": cards,
        "观察哨": watchlist,
        "统计": {
            "卡片总数": len(cards),
            "达标": sum(1 for c in cards if c.get("状态") == "达标"),
            "待补采": sum(1 for c in cards if c.get("状态") == "待补采"),
            "观察哨": len(watchlist),
        },
    }


# ---------- CLI ----------

def validate_card(path, library=None):
    """机检答案卡。重构阶段新增防偷懒：自动复算置信度并与卡片自报值比对
    （堵"凭感觉打'中'最安全"的合理化借口）。"""
    card = json.load(open(path, encoding="utf-8"))
    errors = check_card(card, library)
    warnings = check_independence(card.get("出处", []))
    graded = confidence_grade(card, library)
    if card.get("置信度") and card["置信度"] != graded:
        warnings.append(
            f"置信度自报「{card['置信度']}」，按规则复算为「{graded}」——"
            f"以脚本复算为准并回写卡片")
    return {"errors": errors, "warnings": warnings, "置信度复算": graded}


def main():
    ap = argparse.ArgumentParser(description="gin-answer 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="判定问题类型")
    c.add_argument("--question", required=True)

    v = sub.add_parser("validate", help="机检答案卡")
    v.add_argument("--card", required=True)
    v.add_argument("--library", default=None)

    m = sub.add_parser("manifest", help="汇总 answers-manifest.json")
    m.add_argument("--dir", required=True)
    m.add_argument("--topic", required=True)
    m.add_argument("--library", default=None)

    args = ap.parse_args()

    if args.cmd == "classify":
        print(json.dumps(classify_question(args.question), ensure_ascii=False))
    elif args.cmd == "validate":
        print(json.dumps(validate_card(args.card, args.library), ensure_ascii=False))
    elif args.cmd == "manifest":
        cards = []
        for p in sorted(glob.glob(os.path.join(args.dir, "**", "*.json"),
                                  recursive=True)):
            if os.path.basename(p) == "answers-manifest.json":
                continue
            cards.append(json.load(open(p, encoding="utf-8")))
        manifest = build_manifest(cards, args.topic, args.library)
        out = os.path.join(args.dir, "answers-manifest.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(json.dumps({"manifest": out, "cards": len(cards),
                          "观察哨": len(manifest["观察哨"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
