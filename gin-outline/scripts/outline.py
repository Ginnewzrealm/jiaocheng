#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-outline 工具脚本：缺口判定 / 大纲机检。

规则全部来自 2026-09-06 红阶段基线实测的 7 条真实失败样本：
F1 同一张卡映射全部章节（映射注水）      → 卡映射章节数 > 章节半数 → 警告
F2 缺口判定零标准（清单恒空）            → find_gaps 按主题词 shingles 召回
F3 章节无目标/非动作动词                  → 目标必填 + 动作动词检查
F4 素材召回无规程（留给 SKILL.md 纪律）   → 脚本不管召回，只管机检
F5 素材幽灵引用                          → 文件存在性校验（继承 gin-answer 出处机检）
F6 排序无合法性检查                       → 知识章必须在动作章之前
F7 贯穿案例缺失无检查                     → 钉死检查
另：每张达标卡必须被用到（Socialpranker synthesis gap 校验）→ 未用警告

check_outline 返回字符串列表：❌=error（不许交付） ⚠️=warning（如实报告）
"""
import argparse
import json
import os
import re

# ---------- F2：缺口判定 ----------

def _shingles(topic, n=2):
    """主题词拆 n-字 shingles：'减脂平台期' → {减脂, 脂平, 平台, 台期}"""
    return {topic[i:i + n] for i in range(len(topic) - n + 1)}


def find_gaps(manifest, problems, topic, min_overlap=2):
    """缺口 = 问题清单里与主题相关、但答案卡库没有覆盖的问题。

    红样本 F2：基线的缺口清单恒为空——步骤无标准等于形同虚设。
    相关性判定：问题与主题共享 ≥2 个 shingles（'平台期持续多久'命中
    平台/台期 = 2 → 相关；'减脂和减肥区别'只命中减脂 = 1 → 无关）。
    """
    sh = _shingles(topic)
    covered = {c.get("问题", "") for c in manifest.get("cards", [])}
    gaps = []
    for p in problems:
        q = p.get("text", "")
        overlap = len(sh & _shingles(q, 2)) or (
            len(q) >= 3 and any(q[i:i + 3] in topic for i in range(len(q) - 2)))
        if overlap and overlap >= min_overlap if isinstance(overlap, int) else overlap:
            pass  # 统一在下方处理两种计分
        score = len(sh & _shingles(q, 2))
        if score < min_overlap and len(q) >= 3:
            if any(q[i:i + 3] in topic for i in range(len(q) - 2)):
                score = min_overlap
        if score >= min_overlap and q not in covered:
            gaps.append({"问题": q, "频次": p.get("total_frequency", 0),
                         "说明": "与主题相关但无答案卡覆盖"})
    return gaps


# ---------- F6：章节目标动词分类 ----------

_KNOWLEDGE_MARKERS = ("定义", "概念", "原理", "机制", "背景", "了解", "知道",
                      "理解", "认识", "区分")
_ACTION_VERBS = ("执行", "排查", "计算", "安排", "制定", "应用", "判断",
                 "完成", "操作", "搭建", "复算", "记录", "突破", "调整")


def chapter_stance(chapter):
    """按章节目标动词分类：knowledge（先备知识）/ action（动手操作）/ none。"""
    obj = chapter.get("目标", "")
    if any(m in obj for m in _KNOWLEDGE_MARKERS):
        return "knowledge"
    if any(v in obj for v in _ACTION_VERBS):
        return "action"
    return "none"


# ---------- 机检 ----------

def check_outline(o, manifest, library=None):
    """大纲机检。返回 ❌/⚠️ 字符串列表（空 = 通过）。"""
    out = []
    chapters = o.get("章节", [])
    card_pool = {c.get("问题", ""): c for c in manifest.get("cards", [])}

    # F7 贯穿案例钉死
    if not o.get("贯穿案例"):
        out.append("❌ 缺贯穿案例：动笔前必须钉死一个贯穿全教程的案例/人物"
                   "（course-outline 五决策之一）")

    usage = {}
    for i, ch in enumerate(chapters, 1):
        name = ch.get("章", f"第{i}章")

        # F5a 素材幽灵引用（必须是文件，目录凑数不算——重构期补的借口堵点）
        for mat in ch.get("素材", []):
            if library:
                p = os.path.join(library, mat)
                if not os.path.exists(p):
                    out.append(f"❌ [{name}] 素材不存在：{mat}")
                elif not os.path.isfile(p):
                    out.append(f"❌ [{name}] 素材不是文件：{mat}（写目录路径凑数不行）")

        # F5b 卡片幽灵引用
        for card in ch.get("卡片", []):
            if card not in card_pool:
                out.append(f"❌ [{name}] 卡片不在答案卡库：{card}")
            usage[card] = usage.get(card, 0) + 1

        # F3 章节目标
        obj = ch.get("目标", "")
        if not obj:
            out.append(f"❌ [{name}] 缺章节目标")
        elif re.match(r"^[能会]", obj) and chapter_stance(ch) == "knowledge":
            out.append(f"❌ [{name}] 目标伪装动作：{obj}——'能/会+了解/概念/原理'"
                       f"是知识目标披动作外衣，改成真动作（能判断/能执行/能计算）"
                       f"或去掉能字并确认排序位置")
        elif chapter_stance(ch) == "none":
            out.append(f"❌ [{name}] 目标非动作动词：{obj}（用'能执行/能判断/"
                       f"能计算'开头，知识动词'了解/理解'类须含定义/原理等标记）")

    # F1 映射注水：一张卡映射 ≥3 章且超过章节半数（2 章共享 1 卡是正常复用，
    # 4 章全是同卡才是注水——红阶段基线实测即 4/4 同卡）
    half = (len(chapters) + 1) // 2
    for card, n in usage.items():
        if n >= 3 and n > half:
            out.append(f"⚠️ 映射注水：「{card}」映射了 {n}/{len(chapters)} 章，"
                       f"区分度存疑——一章一角度，同卡复用须有不同要点角度")

    # F6 排序合法性：知识章不得在动作章之后出现
    seen_action = False
    for ch in chapters:
        stance = chapter_stance(ch)
        if stance == "action":
            seen_action = True
        elif stance == "knowledge" and seen_action:
            out.append(f"❌ 排序违规：先备知识章「{ch.get('章','?')}」出现在"
                       f"动作章之后——脚踩西瓜皮，新手会迷路")

    # synthesis gap：达标卡必须被用到（或显式声明不用）
    declared_skip = set(o.get("未采用卡片", []))
    reasons = o.get("未采用理由", {})
    for card in declared_skip:
        if not reasons.get(card):
            out.append(f"⚠️ 未采用卡片缺理由：{card}——弃用也是判断，理由必填")
    used_ok = [q for q, c in card_pool.items() if c.get("状态") == "达标"]
    for q, c in card_pool.items():
        if c.get("状态") == "达标" and q not in usage and q not in declared_skip:
            out.append(f"⚠️ 答案卡未使用：「{q}」达标但没有任何章节映射——"
                       f"要么用掉，要么在'未采用卡片'里声明理由（防答案白找）")
    if used_ok and all(q in declared_skip for q in used_ok):
        out.append("❌ 全部达标卡被弃用——大纲与答案库脱节，说明召回或主题"
                   "定义出了问题，不许带病交付")
    return out


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="gin-outline 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gaps", help="判定缺口（主题相关但无卡覆盖的问题）")
    g.add_argument("--manifest", required=True)
    g.add_argument("--problems", required=True)
    g.add_argument("--topic", required=True)

    c = sub.add_parser("check", help="机检大纲")
    c.add_argument("--outline", required=True)
    c.add_argument("--manifest", required=True)
    c.add_argument("--library", default=None)

    args = ap.parse_args()

    if args.cmd == "gaps":
        manifest = json.load(open(args.manifest, encoding="utf-8"))
        problems = json.load(open(args.problems, encoding="utf-8"))
        if isinstance(problems, dict):
            problems = problems.get("problems") or problems.get("items") or []
        print(json.dumps({"缺口": find_gaps(manifest, problems, args.topic)},
                         ensure_ascii=False, indent=1))
    elif args.cmd == "check":
        o = json.load(open(args.outline, encoding="utf-8"))
        manifest = json.load(open(args.manifest, encoding="utf-8"))
        r = check_outline(o, manifest, args.library)
        print(json.dumps({"结果": r, "errors": sum(1 for s in r if s.startswith("❌")),
                          "warnings": sum(1 for s in r if s.startswith("⚠️"))},
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
