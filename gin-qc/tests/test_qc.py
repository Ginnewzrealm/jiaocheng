#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-qc 回归测试——每条规则对应四层活人感体系的一个真实失败样本。

基线素材（真实文本，非手造）：
- GOOD: /tmp/gin-draft-e2e/ch1.md（过 gin-draft 机检的实战章节）
- BAD:  /tmp/gin-draft-baseline/ch1.md（红阶段裸写章）

运行：python3 -m pytest tests/ -q
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import qc  # noqa: E402

GOOD = "/tmp/gin-draft-e2e/ch1.md"
BAD = "/tmp/gin-draft-baseline/ch1.md"


@pytest.fixture(scope="module")
def good_text():
    return open(GOOD, encoding="utf-8").read()


@pytest.fixture(scope="module")
def bad_text():
    return open(BAD, encoding="utf-8").read()


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


# ---------- CLI ----------

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
