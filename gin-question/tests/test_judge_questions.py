#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_judge_questions.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import judge_questions as jq


def test_passes_real_question():
    r = jq.judge("减脂和减肥有什么区别？", "https://zhihu.com/question/123")
    assert r["passed"] is True, r


def test_rejects_subjective():
    r = jq.judge("减脂好不好？", "https://zhihu.com/question/123")
    assert r["passed"] is False
    assert r["qm3_category"] == "D"


def test_rejects_ai_hint():
    r = jq.judge("可能有人问减脂是什么？", "https://zhihu.com/question/123")
    assert r["passed"] is False
    assert r["qm3_category"] == "A"


def test_rejects_rhetorical():
    r = jq.judge("这还用说吗减脂就是减肥", "https://zhihu.com/question/123")
    assert r["passed"] is False
    assert r["qm3_category"] == "B"


def test_rejects_too_short():
    r = jq.judge("减脂吗？", "https://zhihu.com/question/123")
    assert r["passed"] is False


def test_filter_batch():
    questions = [
        {"text": "减脂是什么？", "source_url": "https://zhihu.com/q1"},
        {"text": "减脂好不好？", "source_url": "https://zhihu.com/q2"},
        {"text": "可能有人问减脂怎么做", "source_url": "https://zhihu.com/q3"},
    ]
    out = jq.filter_questions(questions)
    assert len(out["passed"]) == 1
    assert len(out["rejected"]) == 2


if __name__ == "__main__":
    test_passes_real_question()
    test_rejects_subjective()
    test_rejects_ai_hint()
    test_rejects_rhetorical()
    test_rejects_too_short()
    test_filter_batch()
    print("test_judge_questions OK")
