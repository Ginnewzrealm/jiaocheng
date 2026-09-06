#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-draft 工具脚本：章节机检——"章构件"质检，装配无关。

规则全部来自 2026-09-06 红阶段基线实测（/tmp/gin-draft-baseline/ch1.md）：
F1 章首学习契约缺失   → 开头必须有"写给谁"+"读完能做什么"
F2 章末无可拿走交付物 → 要点总结不算，须 checklist/表格/模板
F3 贯穿案例缺席       → 施工单钉了案例人物，正文必须出场 ≥1
F4 素材锚定缺失       → 关键论断须带来源，锚定率 <60% 不出件
F5 句式密度超标       → "不是A，是B"同一章 >2 次 = 口头禅
另：卡兹克禁区词表机检（三派一致）；素材文件存在性校验。

边界声明：本技能只生产"章构件"，不管这章属于单篇教程还是书——
装配（串篇/组书）是上层的事，未来书籍装配层不动本脚本一字。
"""
import argparse
import json
import os
import re

# ---------- 禁区词表（卡兹克文风，hv-analysis 现成表 + 三篇对标实查） ----------

_BANNED = ["说白了", "本质上", "换句话说", "不可否认", "意味着", "赋能",
           "抓手", "打造闭环", "综上所述", "首先", "其次", "最后",
           "值得注意的是", "不难发现", "在当今", "随着技术"]

# ---------- 句式密度：同一修辞一章 >2 次 = 口头禅 ----------

_RHETORIC_PATTERNS = [
    (re.compile(r"不是[^，。]{1,15}，?(而)?是"), "「不是A，是B」"),
]

# ---------- 章首契约：写给谁 + 读完能做什么 ----------

_CONTRACT_READER = re.compile(r"写给|适合|这篇(章|文章)?.{0,6}(给|适合)")
_CONTRACT_OUTCOME = re.compile(r"(读完|学完|看完).{0,12}(能|可以|会)|"
                               r"你应该能|你将能")

# ---------- 章末交付物：checklist / 表格 / 模板代码块 ----------

_DELIVERABLE_PATTERNS = [
    re.compile(r"- \[ \]"),                    # markdown 待办 = 自查清单
    re.compile(r"^\|.+\|.+\|$", re.M),         # 表格
    re.compile(r"```\w*\n[^`]+```"),           # 可复制模板/代码
]


_L_PATH = re.compile(r"L[1-7][_研究补充]*/\S+")
_DUMP_HEAD = re.compile(r"^\s*(素材|出处|来源|参考|引用)")


def _anchor_hits(text):
    """素材锚定：来源标注/引用句。宽口径——提到素材名/出处/研究引用都算。
    重构期防凑数（只堵清单式贴名，不伤真引用）：
    - 头部带"素材/出处/来源/参考/引用"标签的行 = 清单行，最多算 1；
    - 一行并列 ≥2 个 L 路径（、/，连接）= 贴名行，最多算 1。
    正文里一句真引用连标几处（根据《x》（L3/x）研究）照实计数。"""
    pats = [r"（?素材[:：]", r"（?出处[:：]", r"根据《[^》]+》", r"（[^）]*\d{4}[^）]*）",
            r"L[1-7][_研究补充]*/", r"研究(表明|发现|显示)"]
    hits = 0
    for line in text.splitlines():
        n = sum(len(re.findall(p, line)) for p in pats)
        if n == 0:
            continue
        lpaths = _L_PATH.findall(line)
        if _DUMP_HEAD.search(line) or (len(lpaths) >= 2 and re.search(r"[、，]", line)):
            n = 1
        hits += n
    return hits


def check_chapter(text, materials=None, library=None, case_name=None):
    """机检单章正文。返回 {"errors","warnings","锚定率","禁区词命中",...}。

    materials: 施工单里本章映射的素材数量（list 或 int），用于锚定率分母；
    library: 资料库根路径，校验素材文件存在性。
    """
    errors, warnings = [], []
    materials = materials or []

    # 素材存在性
    if isinstance(materials, (list, tuple)) and library:
        for m in materials:
            if not os.path.exists(os.path.join(library, m)):
                errors.append(f"❌ 素材不存在：{m}")
    n_materials = len(materials) if isinstance(materials, (list, tuple)) else int(materials or 0)

    # F4 锚定率
    hits = _anchor_hits(text)
    denom = max(n_materials, 1)
    rate = min(1.0, hits / (denom * 2))  # 每份素材 2 处锚点 = 满分
    if rate < 0.6:
        errors.append(f"❌ 素材锚定率 {rate:.0%} 低于 60% 红线——论断必须有出处，"
                      f"凭空发挥不出件")

    # F1 章首契约（前 5 行内）
    head = "\n".join(text.splitlines()[:5])
    if not (_CONTRACT_READER.search(head) and _CONTRACT_OUTCOME.search(head)):
        errors.append("❌ 缺章首学习契约：开头必须说明写给谁 + 读完能做到什么"
                      "（对标三篇全有此件）")

    # F2 章末交付物（后 1/3 里找）
    tail = text[len(text) // 3 * 2:]
    if not any(p.search(tail) for p in _DELIVERABLE_PATTERNS):
        errors.append("❌ 章末缺可拿走交付物：自查清单/判断表格/可复制模板"
                      "至少给一样（'本章要点'不算）")

    # F3 贯穿案例
    if case_name and case_name not in text:
        errors.append(f"❌ 贯穿案例「{case_name}」未在正文出场——大纲钉死的案例"
                      f"人物必须出现（用得好不好归 Stage 6）")

    # F5 句式密度
    for pat, name in _RHETORIC_PATTERNS:
        n = len(pat.findall(text))
        if n > 2:
            warnings.append(f"⚠️ {name}句式密度 {n} 次/章（上限 2）——单句是好修辞，"
                            f"密了就是口头禅")

    # 禁区词
    banned_hits = sorted({w for w in _BANNED if w in text}, key=text.index)

    return {"errors": errors, "warnings": warnings,
            "锚定率": round(rate, 2), "禁区词命中": banned_hits,
            "error_count": len(errors), "warning_count": len(warnings)}


def main():
    ap = argparse.ArgumentParser(description="gin-draft 章节机检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="机检单章")
    c.add_argument("--file", required=True)
    c.add_argument("--materials", default="",
                   help="素材相对路径，逗号分隔（或纯数字=素材份数）")
    c.add_argument("--library", default=None)
    c.add_argument("--case", dest="case_name", default=None)
    args = ap.parse_args()

    if args.cmd == "check":
        text = open(args.file, encoding="utf-8").read()
        raw = [s for s in args.materials.split(",") if s]
        if len(raw) == 1 and raw[0].isdigit():
            materials = int(raw[0])
        else:
            materials = raw
        print(json.dumps(check_chapter(text, materials, args.library,
                                       args.case_name),
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
