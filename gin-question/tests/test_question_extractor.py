#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_question_extractor.py — 问题提取来源追踪测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import question_extractor


def test_extract_from_content_marks_source():
    """从正文提取的问题应标记 extracted_from=content。"""
    html = "<html><h1>减脂怎么吃？</h1></html>"
    results = question_extractor.extract_from_content(html, "https://example.com", topic="减脂")
    assert len(results) == 1
    assert results[0]["extracted_from"] == "content"


def test_extract_from_search_title_marks_source():
    """从搜索标题提取的问题应标记 extracted_from=search_title。"""
    result = question_extractor.extract_from_search_result(
        "减脂怎么吃？ - 知乎", "https://www.zhihu.com/question/1", topic="减脂"
    )
    assert result is not None
    assert result["extracted_from"] == "search_title"


def test_extract_from_title_returns_text():
    """从页面标题提取的问题返回归一化文本。"""
    result = question_extractor.extract_from_title("减脂怎么吃？", topic="减脂")
    assert result is not None
    assert "减脂怎么吃" in result


def test_clean_removes_markdown_debris():
    """清洗掉 markdown 残留如用户名、编号、星号。"""
    dirty = "\\n\\nzerosdl\\n\\n**1**\\n\\n女团减脂餐，你看着想吃吗？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "zerosdl" not in cleaned
    assert "**" not in cleaned
    assert "女团减脂餐" in cleaned


def test_clean_removes_heading_markers():
    """清洗掉章节标题标记。"""
    dirty = "\\n\\n## 是什么导致减重平台期？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "##" not in cleaned
    assert "是什么导致减重平台期" in cleaned


def test_clean_removes_social_ui_symbols():
    """清洗掉社交媒体 UI 符号如 [ 。"""
    dirty = "\\n\\n    [减肥和减脂有区别吗？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "[" not in cleaned
    assert "减肥和减脂有区别吗" in cleaned


def test_clean_removes_emoji_prefix():
    """清洗掉表情符号前缀。"""
    dirty = "🔥 你是否曾经被那些广告吸引，尝试过各种减肥方法却总是失败？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "🔥" not in cleaned
    assert "你是否曾经被" in cleaned


def test_clean_removes_article_metadata():
    """清洗掉文章日期作者等元数据。"""
    dirty = "2021-03-20作者：庄志国1、减肥、减重和减脂有什么关系？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "2021" not in cleaned
    assert "作者" not in cleaned
    assert "庄志国" not in cleaned
    assert "减肥、减重和减脂有什么关系" in cleaned


def test_clean_removes_fragment_prefix():
    """清洗掉残缺前缀。"""
    dirty = "：降血壓、防失智還能瘦身梨形身材怎麼瘦？"
    cleaned = question_extractor.clean_question_text(dirty)
    assert "：" not in cleaned
    assert "梨形身材怎麼瘦" in cleaned


def test_rejects_rhetorical_or_guiding_questions():
    """剔除反问、引导句、非真实用户提问。"""
    assert question_extractor.is_real_user_question("你见过瘦的举重运动员吗？") is False
    assert question_extractor.is_real_user_question("揭示传统减肥的三大误区，看看你是否中招了？") is False
    assert question_extractor.is_real_user_question("还在节食减重？") is False


def test_rejects_clickbait_guiding_questions():
    """剔除营销号引导式问句。"""
    assert question_extractor.is_real_user_question("女团减脂餐，你看着想吃吗？") is False
    assert question_extractor.is_real_user_question("减肥成功送学分，你的学校有这么好的操作吗？") is False
    assert question_extractor.is_real_user_question("减肥成功送学分，你心动了吗？") is False
    assert question_extractor.is_real_user_question("关注健康生活新范式是不是一直想减脂，却总在热量计算上犯迷糊？") is False


def test_rejects_list_fragment_leadins():
    """剔除列表引导残缺句。"""
    assert question_extractor.is_real_user_question("很多人在减肥期一段时间后一定会出现几个现象： 1. 怎么镜子里的自己好像瘦了，但体重就是没掉？") is False
    assert question_extractor.is_real_user_question("你是否遭遇过这种困惑 每次减肥时，体重到了一个固定值就死活都减不下去了，为什么？") is False


def test_clean_removes_special_symbols():
    """清理特殊符号如 ‼️ · • 等营销号列表符号。"""
    cleaned = question_extractor.clean_question_text("‼️只吃水果就能瘦？")
    assert "‼️" not in cleaned
    assert "只吃水果就能瘦" in cleaned

    cleaned = question_extractor.clean_question_text("最热内容 · 关于减脂减重，应该怎么吃？")
    assert "·" not in cleaned
    assert "关于减脂减重，应该怎么吃" in cleaned
    assert "最热内容" not in cleaned

    cleaned = question_extractor.clean_question_text("俯卧撑练的是胸     ‼️节食减肥更快？")
    assert "‼️" not in cleaned
    assert "俯卧撑练的是胸" not in cleaned
    assert "节食减肥更快" in cleaned


def test_extract_from_title_rejects_rhetorical():
    """标题/heading 提取也应过滤反问/引导句。"""
    assert question_extractor.extract_from_title("女团减脂餐，你看着想吃吗？", topic="减脂") is None
    assert question_extractor.extract_from_title("减肥成功送学分，你心动了吗？", topic="减脂") is None


if __name__ == "__main__":
    test_extract_from_content_marks_source()
    test_extract_from_search_title_marks_source()
    test_extract_from_title_returns_text()
    test_clean_removes_markdown_debris()
    test_clean_removes_heading_markers()
    test_clean_removes_social_ui_symbols()
    test_clean_removes_emoji_prefix()
    test_clean_removes_article_metadata()
    test_clean_removes_fragment_prefix()
    test_rejects_rhetorical_or_guiding_questions()
    test_rejects_clickbait_guiding_questions()
    test_rejects_list_fragment_leadins()
    test_clean_removes_special_symbols()
    test_extract_from_title_rejects_rhetorical()
    print("test_question_extractor OK")
