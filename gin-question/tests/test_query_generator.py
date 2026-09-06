#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_query_generator.py — 查询生成器测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import query_generator


def test_generates_queries_for_missing_cells():
    """为缺失格子生成非空查询列表。"""
    topic = "减脂"
    expanded_terms = ["减肥", "瘦身"]
    missing = [
        ("基础", "Who"),
        ("旅程", "准备期"),
        ("人群场景", "人群差异"),
    ]
    queries = query_generator.generate(topic, expanded_terms, missing, max_per_cell=1)
    assert len(queries) == 3
    for q in queries:
        assert "perspective" in q
        assert "sub_dimension" in q
        assert "query" in q
        assert topic in q["query"] or any(t in q["query"] for t in expanded_terms)


def test_empty_missing_returns_empty():
    """没有缺失格子时返回空列表。"""
    queries = query_generator.generate("减脂", ["减肥"], [])
    assert queries == []


def test_queries_are_unique():
    """生成的查询在同一 (perspective, sub_dimension) 内不重复。"""
    missing = [("基础", "Who"), ("基础", "Who")]
    queries = query_generator.generate("减脂", [], missing, max_per_cell=1)
    # 去重后应为 1 个
    assert len(set(q["query"] for q in queries)) == 1


if __name__ == "__main__":
    test_generates_queries_for_missing_cells()
    test_empty_missing_returns_empty()
    test_queries_are_unique()
    print("test_query_generator OK")
