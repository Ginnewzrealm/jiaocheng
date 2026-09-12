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

# ---------- 扣主线（hv-analysis 节奏观：偏离后一句拉回，要高频） ----------

_HEAD_STOP = set("的了是在不和有我你他这那也就都又还与或及很更最被把"
                 "让向从到对着呢吗吧啊呀嘛么其之为以及而且因为所以"
                 "一个我们他们你们自己现在时候问题东西情况地方")


def _title_keywords(text, title):
    """从 title（或正文首个 H1）提取 2 字词块（过滤停用块），供扣主线统计。
    用 2 字块而非整词：'是失败还是平台期'整词在正文永远不出现，
    拆成'失败/平台'才能匹配真实回扣句。"""
    src = title or ""
    if not src:
        m = re.search(r"^#\s+(.+)$", text, re.M)
        src = m.group(1) if m else ""
    words = set()
    for m in re.finditer(r"[一-鿿]{2,}", src):
        run = m.group(0)
        if re.fullmatch(r"第[一二三四五六七八九十]+章", run):
            continue
        for i in range(len(run) - 1):
            w = run[i:i + 2]
            if w not in _HEAD_STOP:
                words.add(w)
    return words

# ---------- 推测标注（hv-analysis'敢下判断'：推测必须明说） ----------

_FUTURE_RE = re.compile(r"(未来|接下来|之后|以后|恢复|下一轮|下一步|长期看|短期内)")
_STRONG_RE = re.compile(r"(一定会|必然|必将|百分百|肯定会)")
_HEDGE_RE = re.compile(r"(可能|也许|大概|或许|推测|估计|猜测|预计|大概率|"
                       r"尚未|有待|待验证|证据有限|个案|我的判断|我认为)")

# ---------- 证据密度：引文标注不算"真数字" ----------

_LPATH_RE = re.compile(r"L[1-7][_研究补充]*/\S+")
_YEAR_PAREN_RE = re.compile(r"（[^）]*\d{4}[^）]*）")

# ---------- AI 腔结构特征（2026-09-12 调研批次：Wikipedia/掘金去 AI 味实操） ----------

# 排比三连："不仅…更…还…"式同构并列。真人偶发一句是修辞，密了是 AI 腔。
_PARALLEL_PATTERNS = [
    re.compile(r"不仅[^，。；！？]{1,25}，(而且|更|还|也)"),
    re.compile(r"既[^，。；！？]{1,25}，又"),
    re.compile(r"是[^，。；！？]{1,18}，是[^，。；！？]{1,18}，(还是|也是|又是)"),
    re.compile(r"既要[^，。；！？]{1,18}，又要"),
]
_PARALLEL_LIMIT = 2  # ≥2 处/篇才警告：单句排比是正常修辞

# 段末总结口头禅：段落末句以总结连接词起手。段段有小结是 AI 的典型骨架，
# 真人写作大部分段落直接停在事实上。（"说白了/不难发现"等在 gin-draft
# 禁区词表已拦出现；本条拦的是"位置在段末"这个病灶，与禁区词互补不重复。）
_PARA_SUMMARY_MARKERS = ("所以", "也就是说", "这意味着", "总的来说",
                         "总之", "由此可见")

# "让我们"邀请句：AI 讲解的标志性起手式，真人教程几乎不用。
_RANGWOMEN_RE = re.compile(r"让我们")

# 程度副词/空洞形容词堆砌。"很"不算（真人口语），书面程度词才算。
_INTENSIFIER_RE = re.compile(r"(非常|十分|极其|格外|极为|极大地|大幅度|显著)")
_INTENSIFIER_LIMIT = 3

# ---------- 教程排版构件机检（2026-09-12 调研批次：OpenALG 标题规范/教程结构） ----------

_HEADING_RE = re.compile(r"^(#{1,6})\s", re.M)
_STEP_TITLE_RE = re.compile(r"(怎么|如何|步骤|动手|算出|设置|配置|填出|做出|搭建)")
_BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
_BOLD_LIMIT_PER_1K = 10  # 加粗 >10 处/千字 = 满地加粗 = 无强调


def _heading_levels(text):
    return [len(m.group(1)) for m in _HEADING_RE.finditer(text)]


def _step_sections_missing_lists(text):
    """标题带动作词的 H2 小节（方法节）内没有有序列表的个数。"""
    titles = re.findall(r"^##\s+(.+)$", text, flags=re.M)
    bodies = re.split(r"^##\s+.+$", text, flags=re.M)[1:]
    missing = 0
    for title, body in zip(titles, bodies):
        if _STEP_TITLE_RE.search(title) and not re.search(r"^\s*\d+\.\s", body, re.M):
            missing += 1
    return missing

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


def _para_summary_ratio(text):
    """段末总结口头禅：返回 (命中段落数, 散文段落数)。"""
    total, hit = 0, 0
    for _chars, block in _prose_blocks(text):
        sents = [s.strip() for s in _SENT_SPLIT_RE.split(block) if s.strip()]
        if not sents:
            continue
        total += 1
        last = sents[-1].lstrip("，,、\"'“‘")
        if last.startswith(_PARA_SUMMARY_MARKERS):
            hit += 1
    return hit, total


_L4_ITEMS = [
    "L4 温度感：情绪表达是体感记忆还是知识性描述？（人工判断）",
    "L4 独特性：是否有只有这个作者才会写出来的角度？（人工判断）",
    "L4 姿态：是否滑入'导师教学生'或'品牌做营销'的姿态？（人工判断）",
    "L4 心流：章内通读，注意力有没有断掉？（人工判断）",
]


def check_humanity(text, title=None):
    """对一章正文跑四层活人感机检。返回
    {"errors","warnings","report_items","score","verdict",...}。
    title: 章标题（不给则从正文首个 H1 提取），用于扣主线统计。"""
    errors, warnings = [], []

    # L2：扣主线句（hv-analysis：偏离主线后要高频回扣章题词）
    kws = _title_keywords(text, title)
    prose_lines = [l.strip() for l in text.splitlines()
                   if l.strip() and not l.lstrip().startswith(("#", "|", ">",
                                                               "- ", "* "))]
    if len(prose_lines) >= 5 and kws:
        pullback = sum(1 for l in prose_lines if any(k in l for k in kws))
        if pullback < 2:
            warnings.append(f"⚠️ 扣主线句缺席：{len(prose_lines)} 行散文只有 "
                            f"{pullback} 行回扣章题词——形散神也散，偏离后"
                            f"要有一句把读者拉回主线")

    # L3：推测标注（hv-analysis'敢下判断'：推测明说，不装作事实）
    for sent in _SENT_SPLIT_RE.split(text):
        s = sent.strip()
        if not s or len(s) > 120:
            continue
        if (_FUTURE_RE.search(s) and _STRONG_RE.search(s)
                and not _HEDGE_RE.search(s)):
            warnings.append(f"⚠️ 未标注推测：'{s[:25]}…'——对未来下强断言"
                            f"要有'可能/推测/证据有限'类标注，别装作事实")
            break

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

    # L3：排比三连（AI 腔最强结构特征，2026-09-12 调研批次）
    n_parallel = sum(len(p.findall(text)) for p in _PARALLEL_PATTERNS)
    if n_parallel >= _PARALLEL_LIMIT:
        warnings.append(f"⚠️ 排比三连 {n_parallel} 处/篇（≥{_PARALLEL_LIMIT}）"
                        f"——'不仅…更…还…'式同构并列是 AI 腔的典型骨架，"
                        f"单句是好修辞，密了就是口头禅")

    # L3：段末总结口头禅（段段以'所以/也就是说'收尾 = AI 骨架）
    para_hit, para_total = _para_summary_ratio(text)
    if para_total >= 3 and para_hit / para_total > 0.3 and para_hit >= 2:
        warnings.append(f"⚠️ 段末总结口头禅：{para_hit}/{para_total} 个段落"
                        f"以'所以/也就是说/这意味着'收尾——段段有小结是"
                        f"AI 的典型骨架，真人写作大部分段落直接停在事实上")

    # L3："让我们"邀请句（AI 讲解标志性起手式）
    if _RANGWOMEN_RE.search(text):
        warnings.append("⚠️ '让我们…'邀请句——AI 讲解的标志性起手式，"
                        "真人教程几乎不用，直接陈述即可")

    # L3：程度副词堆砌（'很'不算，书面程度词才算）
    n_intensifier = len(_INTENSIFIER_RE.findall(text))
    if n_intensifier >= _INTENSIFIER_LIMIT:
        warnings.append(f"⚠️ 程度副词堆砌 {n_intensifier} 次/篇"
                        f"（{sorted(set(_INTENSIFIER_RE.findall(text)))}，"
                        f"≥{_INTENSIFIER_LIMIT}）——删掉程度词，让数字和事实"
                        f"自己说话")

    # 排版构件：H 层级连续性（❌ 跳级）与孤儿 H3（⚠️，OpenALG 规范）
    levels = _heading_levels(text)
    for a, b in zip(levels, levels[1:]):
        if b - a > 1:
            errors.append(f"❌ 标题层级跳级：H{a} 直接下 H{b}——标题层级必须"
                          f"连续，跳级是排版事故（H3 不存在就先在 H2 下补散文）")
            break
    if levels.count(3) == 1 and levels.count(2) >= 2:
        warnings.append("⚠️ 孤立 H3：全文仅 1 个 H3 无配对——H3 只在节内步骤"
                        f"分组需要导航时才上，单蹦一个是不完整结构，要么补成对"
                        f"要么降回正文")

    # 排版构件：方法节缺步骤结构（'怎么做'必须有步骤呈现，这是教程的核心构件）
    n_missing_steps = _step_sections_missing_lists(text)
    if n_missing_steps:
        warnings.append(f"⚠️ {n_missing_steps} 个方法节（标题带'怎么/如何/算出'"
                        f"等动作词）通篇无有序列表——教程的'怎么做'要用步骤"
                        f"呈现：1. 2. 3.，每项动作开头")

    # 排版构件：加粗密度
    n_bold = len(_BOLD_RE.findall(text))
    if n_chars >= 300 and n_bold * 1000 > _BOLD_LIMIT_PER_1K * n_chars:
        warnings.append(f"⚠️ 加粗 {n_bold} 处（约 {n_bold * 1000 // n_chars} 处/千字，"
                        f"上限 {_BOLD_LIMIT_PER_1K}）——满地加粗=处处强调=无强调，"
                        f"只留真正的关键句")

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
