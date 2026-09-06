#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-qc 工具脚本：教程章节四层活人感质检。

复用 gin-wechat-article-quality 的 L1-L4 四层体系，改造为教程场景：
- L1 硬性规则（自动扫描）：段落 ≤300 字
- L2 风格一致性（模式匹配）：长短句交替、疑问句对话感
- L3 内容质量（机器可判子集）：证据密度、认知灰度、身份共鸣、结构整齐度
- L4 活人感终审（主观判断项，只出报告项不进评分）

与 gin-draft 分工：gin-draft 管构件合格（锚定/契约/交付物/案例/密度/禁区词），
本脚本不重复；本脚本管"读起来像人写的"。

评分：100 起扣，任一 hard-fail 直接不通过，normal 项每项 -5；
≥85 通过，70-84 通过但提示 minor 问题，<70 不通过返回修改。
"""
import argparse
import json
import re
import statistics

# ---------- L1：硬性规则 ----------

_PARA_LIMIT = 300  # wechat L1-7：段落不超过 300 字

# ---------- L3：认知灰度（绝对化词汇，"不一定"是留余地的说法，豁免） ----------

_ABSOLUTE_RE = re.compile(r"(?<![不必])(一定|绝对|百分百|必然|肯定会)")

# ---------- 证据密度：引文标注不算"真数字" ----------

_LPATH_RE = re.compile(r"L[1-7][_研究补充]*/\S+")
_YEAR_PAREN_RE = re.compile(r"（[^）]*\d{4}[^）]*）")

# ---------- L2：句子切分 ----------

_SENT_SPLIT_RE = re.compile(r"[。！？!?；;…]+")


def _prose_blocks(text):
    """正文块（跳过大标题行与表格行），返回 [(chars, block)]。"""
    blocks = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith(("#", "|", ">")) for l in lines):
            continue
        chars = len(re.sub(r"\s", "", block))
        blocks.append((chars, block))
    return blocks


def _bullet_runs(text):
    """连续 bullet 行组成的块列表。每个元素是 (起始行号, 行数)。"""
    runs, start, count = [], None, 0
    for i, line in enumerate(text.splitlines()):
        if line.lstrip().startswith(("- ", "* ")):
            if start is None:
                start, count = i, 1
            else:
                count += 1
        else:
            if start is not None:
                runs.append((start, count))
                start, count = None, 0
    if start is not None:
        runs.append((start, count))
    return runs


def _sentences(text):
    parts = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    # 表格行/引用行不参与句长统计
    return [s for s in parts
            if not s.lstrip().startswith(("|", ">", "#", "- ", "* "))]


def _evidence_digits(text):
    """真数字：剥掉 L 路径和引文年份标注后剩余的阿拉伯数字个数。"""
    cleaned = _LPATH_RE.sub("", text)
    cleaned = _YEAR_PAREN_RE.sub("", cleaned)
    return len(re.findall(r"\d", cleaned))


def _verdict_of(score):
    if score >= 85:
        return "通过"
    if score >= 70:
        return "通过但提示 minor 问题"
    return "不通过"


_L4_ITEMS = [
    "L4 温度感：情绪表达是体感记忆还是知识性描述？（人工判断）",
    "L4 独特性：是否有只有这个作者才会写出来的角度？（人工判断）",
    "L4 姿态：是否滑入'导师教学生'或'品牌做营销'的姿态？（人工判断）",
    "L4 心流：章内通读，注意力有没有断掉？（人工判断）",
]


def check_humanity(text):
    """对一章正文跑四层活人感机检。返回
    {"errors","warnings","report_items","score","verdict",...}。"""
    errors, warnings = [], []

    # L1：段落 ≤300 字（硬规则）
    for chars, block in _prose_blocks(text):
        if chars > _PARA_LIMIT:
            head = block.strip().replace("\n", "")[:20]
            errors.append(f"❌ 段落 {chars} 字超过 {_PARA_LIMIT} 字上限"
                          f"（'{head}…'）——一堵文字墙，拆开")

    # L2：长短句交替（中位数集中度：多数句子挤在中位数 ±20% 内 = 整齐节奏，
    # 防止塞一句超长句拉方差蒙混）
    sents = _sentences(text)
    if len(sents) >= 5:
        lens = [len(s) for s in sents]
        med = statistics.median(lens)
        near = sum(1 for l in lens if 0.8 * med <= l <= 1.2 * med)
        if near / len(lens) >= 0.7:
            warnings.append(f"⚠️ 句长整齐划一（{near}/{len(lens)} 句挤在"
                            f"中位数 {med:.0f} 字 ±20% 内）——无长短句交替，"
                            f"AI 输出典型节奏")

    # L2：疑问句对话感
    n_q = len(re.findall(r"[？?]", text))
    if n_q == 0:
        warnings.append("⚠️ 全章零疑问句——单向输出无对话感，真人讲解会自然抛问")

    # L3：证据密度（每 800 字至少 1 行含真数字，且按行分布——
    # 一行贴满数字不算数；引文年份和素材路径也不算数）
    n_chars = len(re.sub(r"\s", "", text))
    required = max(1, n_chars // 800)
    digit_lines = 0
    for line in text.splitlines():
        if line.lstrip().startswith(("#", "|", ">")):
            continue
        if _evidence_digits(line) > 0:
            digit_lines += 1
    if n_chars >= 300 and digit_lines < required:
        warnings.append(f"⚠️ 证据密度不足：{n_chars} 字需要 ≥{required} 行含真数字"
                        f"（现 {digit_lines} 行）——空对空论述，"
                        f"把具体数据/案例揉进正文各处，别一行贴完")

    # L3：认知灰度
    abs_hits = sorted({m.group(1) for m in _ABSOLUTE_RE.finditer(text)})
    if abs_hits:
        warnings.append(f"⚠️ 绝对化词汇 {abs_hits}——核心判断留灰度，"
                        f"把'一定/绝对'换成条件和概率")

    # L3：身份共鸣（明确称呼目标读者）
    if n_chars >= 300 and text.count("你") < 2:
        warnings.append("⚠️ 全章几乎没有'你'——教科书腔，至少 1 处明确"
                        "称呼目标读者")

    # L3：结构过分整齐（bullet 块背靠背，中间无正文论述）
    runs = _bullet_runs(text)
    lines = text.splitlines()
    for (s1, c1), (s2, c2) in zip(runs, runs[1:]):
        between = [l for l in lines[s1 + c1:s2] if l.strip()]
        if not between:  # 中间只有空行
            warnings.append("⚠️ 两个列表块背靠背、中间无正文论述——"
                            "结构过分整齐，列表之间要有人话过渡")
            break

    score = 100 - 5 * len(warnings)
    verdict = "不通过" if errors else _verdict_of(score)
    return {"errors": errors, "warnings": warnings,
            "report_items": list(_L4_ITEMS), "score": score, "verdict": verdict,
            "error_count": len(errors), "warning_count": len(warnings)}


def main():
    ap = argparse.ArgumentParser(description="gin-qc 章节活人感质检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="质检单章")
    c.add_argument("--file", required=True)
    args = ap.parse_args()

    if args.cmd == "check":
        text = open(args.file, encoding="utf-8").read()
        print(json.dumps(check_humanity(text), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
