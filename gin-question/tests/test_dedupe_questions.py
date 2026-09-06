#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_dedupe_questions.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import dedupe_questions as dq


def test_exact_dedupe():
    qs = [{"text": "减脂是什么？"}, {"text": "减脂是什么？"}]
    out = dq.dedupe(qs)
    assert len(out["unique"]) == 1


def test_semantic_dedupe():
    qs = [{"text": "减脂是什么？"}, {"text": "什么是减脂？"}]
    out = dq.dedupe(qs)
    assert len(out["unique"]) == 1


def test_subset_dedupe():
    qs = [{"text": "上班族减脂期间应该怎么吃？"}, {"text": "减脂怎么吃？"}]
    out = dq.dedupe(qs)
    assert len(out["unique"]) == 1
    assert "减脂怎么吃？" in out["unique"][0].get("duplicates", [])


def test_keeps_distinct():
    qs = [{"text": "减脂是什么？"}, {"text": "减脂怎么做？"}]
    out = dq.dedupe(qs)
    assert len(out["unique"]) == 2


def test_dedupe_merges_sources_of_semantic_duplicates():
    """语义重复项（含传递性合并）的 sources 应合并到保留项。"""
    qs = [
        {"text": "减脂是什么？", "sources": {"https://a.com": 1}},
        {"text": "到底减脂是什么？", "sources": {"https://b.com": 1}},
        {"text": "究竟减脂是什么？", "sources": {"https://c.com": 1}},
    ]
    out = dq.dedupe(qs)
    assert len(out["unique"]) == 1
    kept = out["unique"][0]
    assert kept["sources"]["https://a.com"] == 1
    assert kept["sources"]["https://b.com"] == 1
    assert kept["sources"]["https://c.com"] == 1


if __name__ == "__main__":
    test_exact_dedupe()
    test_semantic_dedupe()
    test_subset_dedupe()
    test_keeps_distinct()
    test_dedupe_merges_sources_of_semantic_duplicates()
    print("test_dedupe_questions OK")
