#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-qc 回归测试——每条规则对应四层活人感体系的一个真实失败样本。

基线素材（真实文本，非手造），按优先级查找：
- GOOD: tests/fixtures/good_ch1.md（仓库内置，推荐）→ /tmp/gin-draft-e2e/ch1.md（e2e 产物）
- BAD:  tests/fixtures/bad_ch1.md（仓库内置，推荐）→ /tmp/gin-draft-baseline/ch1.md（e2e 产物）

素材均不存在时，依赖它们的测试 skip（不 error）——把真实章节放进 tests/fixtures/ 即恢复执行。
补齐方式：跑一次 gin-draft 减脂 e2e，把过机检章和裸写章分别复制为上述两个 fixture 文件。

运行：python3 -m pytest tests/ -q
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import qc  # noqa: E402

_HERE = os.path.dirname(__file__)

GOOD_CANDIDATES = [
    os.path.join(_HERE, "fixtures", "good_ch1.md"),
    "/tmp/gin-draft-e2e/ch1.md",
]
BAD_CANDIDATES = [
    os.path.join(_HERE, "fixtures", "bad_ch1.md"),
    "/tmp/gin-draft-baseline/ch1.md",
]


def _load_first_existing(candidates, label):
    for path in candidates:
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()
    pytest.skip(f"基线素材不存在：{label}（把真实章节放进 tests/fixtures/ 或先跑 gin-draft 减脂 e2e）")


@pytest.fixture(scope="module")
def good_text():
    return _load_first_existing(GOOD_CANDIDATES, "GOOD 过机检章")


@pytest.fixture(scope="module")
def bad_text():
    return _load_first_existing(BAD_CANDIDATES, "BAD 裸写章")


# ---------- L1 硬性规则 ----------

def test_paragraph_over_300_chars_flagged():
    """wechat L1-7：段落不超过 300 字。一堵文字墙直接拦。"""
    long_para = "这是一段话。" * 60  # ~360 字
    r = qc.check_humanity(long_para)
    assert any("段落" in e for e in r["errors"])


def test_normal_paragraphs_ok():
    text = "短段落一。\n\n短段落二，也不长。"
    r = qc.check_humanity(text)
    assert not any("段落" in e for e in r["errors"])


# ---------- L3 语言债：结构过分整齐 ----------

def test_back_to_back_bullet_blocks_flagged():
    """两个 bullet 列表块中间只有空行、没有正文论述 = 结构过分整齐（AI 特征）。"""
    text = ("论述段落，先说清楚一件事。\n\n"
            "- 要点一\n- 要点二\n\n"
            "- 又一\n- 又来")
    r = qc.check_humanity(text)
    assert any("结构" in w for w in r["warnings"])


def test_bullets_with_prose_between_ok():
    text = ("论述段落一。\n\n- 要点一\n- 要点二\n\n"
            "中间有一段正文展开论述。\n\n- 又一\n- 又来")
    r = qc.check_humanity(text)
    assert not any("结构" in w for w in r["warnings"])


# ---------- L2 风格一致性：长短句交替 ----------

def test_uniform_sentence_length_flagged():
    """全文句子长度整齐划一 = 无长短句交替（AI 输出的典型节奏）。"""
    # 每句都是 10 个字左右，整齐排列
    text = "减脂过程当中体重下降减慢属于正常的现象。" + \
           "体重停止变化并不意味着你的方法已经失效。" + \
           "身体需要一段时间来适应新的能量摄入水平。" + \
           "保持记录才能帮助你判断真实的变化趋势。" + \
           "短期波动更多是水分而不是脂肪的变化。"
    r = qc.check_humanity(text)
    assert any("句长" in w or "长短句" in w for w in r["warnings"])


def test_varied_sentence_length_ok(good_text):
    r = qc.check_humanity(good_text)
    assert not any("句长" in w or "长短句" in w for w in r["warnings"])


def test_one_outlier_sentence_does_not_save_uniform_rhythm():
    """借口：塞一句超长句拉大方差，其余句子照旧整齐。
    堵法：看中位数集中度——多数句子挤在中位数 ±20% 内就是整齐节奏。"""
    uniform = "减脂过程当中体重下降减慢属于正常的现象。" * 9  # 每句 19 字
    outlier = "而如果你在这个时候选择放弃，那么你之前所有的努力都将付诸东流，体重会在很短的时间内反弹回来，甚至超过原来的水平，这是很多研究都反复证实过的结论。"
    r = qc.check_humanity(uniform + outlier)
    assert any("句长" in w or "长短句" in w for w in r["warnings"])


# ---------- L2 风格一致性：疑问句对话感 ----------

def test_zero_questions_flagged():
    """全章零疑问句 = 单向输出无对话感（真人讲解会自然抛问）。"""
    text = "减脂过程中体重停滞是正常现象。身体在适应新的摄入水平。" * 8
    r = qc.check_humanity(text)
    assert any("疑问" in w for w in r["warnings"])


def test_questions_present_ok(good_text):
    r = qc.check_humanity(good_text)
    assert not any("疑问" in w for w in r["warnings"])


# ---------- L3 内容质量：证据密度 ----------

def test_low_evidence_density_flagged():
    """wechat L3-8：每 800 字至少 1 个具体数据/案例。通篇无数字 = 空对空。"""
    text = "体重停滞是很常见的现象，很多人会遇到这种情况。" * 20  # 400 字，零数字
    r = qc.check_humanity(text)
    assert any("证据密度" in w for w in r["warnings"])


def test_evidence_density_ok(good_text):
    r = qc.check_humanity(good_text)
    assert not any("证据密度" in w for w in r["warnings"])


def test_lpath_and_citation_years_not_counted_as_evidence():
    """借口：贴 L3/素材路径 和（2024）引文年份也算'有数字'。
    证据密度只认真数字（数据/时间/量），引文标注不算数。"""
    text = "根据某研究（素材：L3/科学网，2024），体重会停滞。" * 12
    r = qc.check_humanity(text)
    assert any("证据密度" in w for w in r["warnings"])


def test_digit_dumping_in_one_line_not_enough():
    """借口：一行贴满数字（'掉了8公斤，200千卡，1200千卡，85%'）凑证据密度。
    堵法：按'含真数字的行数'算，每 800 字至少 1 行有数字，且要分布在不同行。"""
    prose = "体重停滞是很常见的现象，很多人会遇到这种情况。" * 75  # ~1650 字无数字
    text = prose + "\n\n数据：8公斤 200千卡 1200千卡 85% 6个月 4周。"
    r = qc.check_humanity(text)
    assert any("证据密度" in w for w in r["warnings"])


# ---------- L3 内容质量：认知灰度 ----------

def test_absolute_words_flagged():
    """wechat L2-6：核心判断不用绝对化词汇。"""
    text = "这个方法一定能成功。坚持就绝对有效。百分百能突破平台期。" * 4
    r = qc.check_humanity(text)
    assert any("绝对化" in w for w in r["warnings"])


def test_no_absolute_words_ok(good_text):
    r = qc.check_humanity(good_text)
    assert not any("绝对化" in w for w in r["warnings"])


# ---------- L3 内容质量：身份共鸣 ----------

def test_missing_reader_address_flagged():
    """wechat L3-10：至少 1 处明确称呼目标读者。通篇无'你' = 教科书腔。"""
    text = (("体重停滞是减脂过程中的常见现象。身体会产生代谢适应。"
             "记录饮食和运动有助于判断进展情况。" * 8)
            + "对吧？")  # 疑问句不命中，凑够长度后只留'称呼'一个变量
    assert len(re.sub(r"\s", "", text)) >= 300
    r = qc.check_humanity(text)
    assert any("称呼" in w or "身份共鸣" in w for w in r["warnings"])


def test_reader_address_ok(good_text):
    r = qc.check_humanity(good_text)
    assert not any("称呼" in w or "身份共鸣" in w for w in r["warnings"])


# ---------- 评分与判定 ----------

def test_hard_fail_blocks_pass():
    """任一 error（L1 硬规则）→ 整体不通过，分数再高也没用。"""
    long_para = "这是一段话。" * 60
    r = qc.check_humanity(long_para)
    assert r["verdict"] == "不通过"


def test_normal_items_deduct_5_each():
    """normal 项（warning）每项 -5。"""
    text = ("体重停滞是很常见的现象，很多人会遇到这种情况。" * 20  # 证据密度命中
            + "\n\n这个方法一定能成功。" * 4)  # 绝对化命中
    r = qc.check_humanity(text)
    assert r["score"] == 100 - 5 * r["warning_count"]
    assert r["warning_count"] >= 2


def test_scoring_bands():
    assert qc._verdict_of(100) == "通过"
    assert qc._verdict_of(85) == "通过"
    assert qc._verdict_of(70) == "通过但提示 minor 问题"
    assert qc._verdict_of(69) == "不通过"


# ---------- 集成：真实章 ----------

def test_good_chapter_passes(good_text):
    """过 gin-draft 的实战章，活人感机检必须也过（errors=0，verdict 通过）。"""
    r = qc.check_humanity(good_text)
    assert r["errors"] == []
    assert r["verdict"] in ("通过", "通过但提示 minor 问题")


def test_report_items_include_l4_subjective_items(good_text):
    """L4 活人感终审（温度感/独特性/姿态/心流）不进评分，但报告项必须在场，
    供人终审时逐项过脑子。"""
    r = qc.check_humanity(good_text)
    labels = " ".join(r["report_items"])
    for key in ("温度感", "独特性", "姿态", "心流"):
        assert key in labels


# ---------- 对标 hv-analysis 写作方法论（用户拍板 2026-09-06） ----------

def test_no_mainline_pullback_flagged():
    """扣主线句（hv-analysis 节奏观）：偏离主线后要用一句拉回。
    通篇零回扣章题词 = 只发散文不散文、形散神也散 → 拦。"""
    text = ("减脂平台期是什么。\n\n" + "它有很多表现和成因值得仔细分析。\n\n" * 4 +
            "我们需要从多个角度看待这个现象。\n\n" * 4 + "对吧？")
    r = qc.check_humanity(text, title="减脂平台期")
    assert any("扣主线" in w or "主线" in w for w in r["warnings"])


def test_mainline_pullback_ok(good_text):
    r = qc.check_humanity(good_text, title="体重不动了，是失败还是平台期？")
    assert not any("扣主线" in w or "主线" in w for w in r["warnings"])


def test_unflagged_speculation_flagged():
    """hv-analysis'敢下判断'：推测必须明确标注。
    '未来一定会反弹'这类无标注断言 → 拦（同时命中绝对化，但推测标注要独立成项）。"""
    text = ("体重停滞后恢复进食，体重一定会大幅反弹。" * 6 + "对吧？")
    r = qc.check_humanity(text, title="体重停滞")
    assert any("推测" in w or "标注" in w for w in r["warnings"])


def test_flagged_speculation_ok():
    text = ("体重停滞后恢复进食，体重可能会反弹——这是我的推测，目前只有个案观察。"
            * 3 + "对吧？")
    r = qc.check_humanity(text, title="体重停滞")
    assert not any("推测" in w or "标注" in w for w in r["warnings"])


# ---------- CLI ----------


# ---------- AI 腔结构特征（2026-09-12 调研批次：排比/段末总结/让我们/程度副词） ----------

def test_parallel_triplet_flagged():
    """排比三连（'不仅…更…还…'式同构并列）是 AI 腔最强结构特征。
    一篇出现 ≥2 处 → 警告；真人偶发一句是修辞。"""
    text = ("减脂不仅是少吃，更是重新理解身体的能量账。你要先算清消耗。"
            "这个过程中，既能保住肌肉，又能稳定情绪。" * 3
            + "坚持记录你就会发现变化。")
    r = qc.check_humanity(text)
    assert any("排比" in w for w in r["warnings"])


def test_single_parallel_ok():
    """一处排比是正常修辞，不警告。"""
    parallel_once = "减脂不仅是少吃，更是重新理解身体的能量账。"
    filler = ("体重停滞是身体的适应机制在起作用，通常持续两到三周。"
              "水分回流占了反弹的大头，别急着加运动量。"
              "记录饮食能帮你区分水分和脂肪，数据比体重秤诚实。")
    r = qc.check_humanity(parallel_once + filler * 3)
    assert not any("排比" in w for w in r["warnings"])


def test_paragraph_summary_tic_flagged():
    """段末总结口头禅：几乎每段都以'所以/也就是说/这意味着'收尾，
    段段有小结是 AI 的典型骨架。真人写作大部分段落直接停在事实上。"""
    para1 = "体重停滞是身体的适应机制在起作用。所以不用慌。"
    para2 = "水分回流占了反弹的大头。也就是说不是脂肪回来了。"
    para3 = "记录饮食能帮你区分两者。这意味着数据比体重秤诚实。" * 8
    r = qc.check_humanity(para1 + "\n\n" + para2 + "\n\n" + para3)
    assert any("段末" in w or "总结" in w for w in r["warnings"])


def test_natural_paragraph_endings_ok():
    """段落直接停在事实上、没有总结口头禅 → 不警告。"""
    text = ("体重停滞是身体的适应机制在起作用，通常持续两到三周。"
            "水分回流占了反弹的大头，别急着加运动量。" * 5)
    r = qc.check_humanity(text)
    assert not any("段末" in w or "总结" in w for w in r["warnings"])


def test_rangwomen_invitation_flagged():
    """'让我们…'邀请句是 AI 讲解的标志性起手式，真人教程几乎不用。"""
    text = ("让我们先来看看体重为什么会停滞。" * 6 + "对吧？")
    r = qc.check_humanity(text)
    assert any("让我们" in w for w in r["warnings"])


def test_intensifier_density_flagged():
    """程度副词/空洞形容词堆砌：'非常/十分/极大地/显著' ≥3 次/篇 → 警告。
    真人口语有'很'，但书面堆程度词是 AI 味。"""
    text = ("这个方法非常有效，效果十分显著。" * 5 + "坚持就会看到变化。")
    r = qc.check_humanity(text)
    assert any("程度" in w for w in r["warnings"])


def test_intensifier_spare_ok():
    text = ("这个方法很朴素：每天记录饮食。坚持两三周就能看到趋势。" * 4)
    r = qc.check_humanity(text)
    assert not any("程度" in w for w in r["warnings"])


# ---------- 教程排版构件机检（2026-09-12 调研批次：H层级/步骤结构/加粗密度） ----------

def test_heading_level_skip_flagged():
    """H2 直接下 H4 = 层级跳级 ❌——教程的标题层级必须连续，跳级是排版事故。"""
    text = "# 篇名\n\n## 第一节\n\n正文内容，说一件事。\n\n#### 突然跳到四级\n\n正文。"
    r = qc.check_humanity(text)
    assert any("跳级" in e for e in r["errors"])


def test_lone_h3_flagged():
    """全文仅 1 个 H3 = 孤儿标题 ⚠️（OpenALG 规范：lone heading）。
    H3 只在节内步骤分组需要导航时才上，单蹦一个是不完整结构。"""
    text = "# 篇名\n\n## 第一节\n\n正文内容。\n\n### 唯一的细分\n\n正文。\n\n## 第二节\n\n正文。"
    r = qc.check_humanity(text)
    assert any("孤立" in w or "孤儿" in w for w in r["warnings"])


def test_multiple_h3_ok():
    text = ("# 篇名\n\n## 第一节\n\n### 细分一\n\n正文内容。\n\n### 细分二\n\n正文。"
            "\n\n## 第二节\n\n正文。")
    r = qc.check_humanity(text)
    assert not any("孤立" in w or "孤儿" in w for w in r["warnings"])


def test_method_section_without_steps_flagged():
    """标题带动作词（怎么/如何/算出/设置…）的小节 = 方法节，
    方法节通篇散文、没有一个有序列表 = 缺步骤结构 ⚠️——教程的'怎么做'
    必须用步骤呈现，这是'像教程'的核心构件。"""
    text = ("# 篇名\n\n## 怎么算出你的热量缺口\n\n"
            "先算消耗，再定缺口，最后填进表格。说起来很简单。" * 4)
    r = qc.check_humanity(text)
    assert any("步骤" in w for w in r["warnings"])


def test_method_section_with_steps_ok():
    text = ("# 篇名\n\n## 怎么算出你的热量缺口\n\n"
            "按三步走：\n\n1. 算出你的 TDEE\n2. 选定缺口档位\n3. 填进每日目标\n\n"
            "每一步都要落到数字上。对吧？")
    r = qc.check_humanity(text)
    assert not any("步骤" in w for w in r["warnings"])


def test_bold_density_flagged():
    """加粗密度 >10 处/千字 ⚠️——满地加粗=处处强调=无强调。"""
    unit = "**关键概念**很重要，**核心方法**要注意，**这个步骤**别跳过。"
    text = "# 篇名\n\n" + unit * 12  # 36 处加粗，约 430 字 → 远超阈值
    r = qc.check_humanity(text)
    assert any("加粗" in w for w in r["warnings"])


def test_bold_spare_ok():
    text = ("# 篇名\n\n体重停滞是身体的适应机制，通常持续两到三周。"
            "水分回流占了反弹大头，**别急着加运动量**。记录饮食能帮你区分两者。" * 3)
    r = qc.check_humanity(text)
    assert not any("加粗" in w for w in r["warnings"])


def test_cli_check_outputs_json(tmp_path):
    import json
    import subprocess
    p = tmp_path / "ch.md"
    p.write_text("短段落。\n\n另一个短段落。", encoding="utf-8")
    out = subprocess.run(
        [sys.executable,
         os.path.join(os.path.dirname(__file__), "..", "scripts", "qc.py"),
         "check", "--file", str(p)],
        capture_output=True, text=True)
    r = json.loads(out.stdout)
    assert "errors" in r and "warnings" in r and "score" in r
