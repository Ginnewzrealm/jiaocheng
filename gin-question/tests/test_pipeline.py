#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_pipeline.py — 端到端流水线测试。"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pipeline


def build_sample_manifest():
    return {
        "topic": "减脂",
        "expanded_terms": ["减肥", "瘦身"],
        "retrieval_rounds": 1,
        "search_results": [
            {
                "perspective": "基础",
                "sub_dimension": "What",
                "query": "减脂是什么",
                "results": [
                    {"title": "减脂和减肥有什么区别？ - 知乎", "url": "https://www.zhihu.com/question/1"},
                    {"title": "减脂的科学原理是什么", "url": "https://www.sohu.com/a/1"},
                ],
            },
            {
                "perspective": "旅程",
                "sub_dimension": "瓶颈期",
                "query": "减脂平台期怎么办",
                "results": [
                    {"title": "进入减脂平台期，该怎么办？ - 知乎", "url": "https://www.zhihu.com/question/2"},
                ],
            },
        ],
        "fetched_pages": {
            "https://www.zhihu.com/question/1": "<html><h1>减脂和减肥有什么区别？</h1></html>",
        },
    }


def test_pipeline_run():
    manifest = build_sample_manifest()
    tmpdir = tempfile.mkdtemp()
    try:
        result = pipeline.run(manifest, tmpdir, is_abstract=False)
        assert result["confirmed_count"] + result["pending_count"] >= 1
        assert os.path.exists(os.path.join(tmpdir, "problem_list.json"))
        assert os.path.exists(os.path.join(tmpdir, "problem_list.md"))
        assert os.path.exists(os.path.join(tmpdir, "audit_report.json"))

        with open(os.path.join(tmpdir, "problem_list.json"), "r", encoding="utf-8") as f:
            pl = json.load(f)
        assert pl["topic"] == "减脂"
        assert "problems" in pl
    finally:
        shutil.rmtree(tmpdir)


def test_pipeline_tracks_source_and_reachability_in_audit():
    """审计报告应包含问题来源统计和源可触达率。"""
    manifest = {
        "topic": "减脂",
        "expanded_terms": ["减肥"],
        "retrieval_rounds": 1,
        "search_results": [
            {
                "perspective": "基础",
                "sub_dimension": "What",
                "query": "减脂是什么",
                "results": [
                    {"title": "减脂怎么吃？", "url": "https://example.com/1"},
                    {"title": "减脂原理是什么？", "url": "https://example.com/2"},
                ],
            },
        ],
        "fetched_pages": {
            "https://example.com/1": "<html><h1>减脂怎么吃？</h1></html>",
        },
    }
    tmpdir = tempfile.mkdtemp()
    try:
        result = pipeline.run(manifest, tmpdir, is_abstract=False)
        assert result["confirmed_count"] + result["pending_count"] >= 1

        with open(os.path.join(tmpdir, "audit_report.json"), "r", encoding="utf-8") as f:
            audit = json.load(f)
        assert "from_fetched_pages" in audit
        assert "from_search_title" in audit
        assert "source_reachability" in audit
        # 2 个 URL，1 个抓取成功，可触达率 0.5
        assert audit["source_reachability"] == 0.5
    finally:
        shutil.rmtree(tmpdir)


def test_cross_url_semantic_duplicate_aggregates_sources_to_confirmed():
    """语义相同但表述不同的问题跨 URL 出现时，应合并来源并提升为 confirmed。"""
    manifest = {
        "topic": "减脂",
        "expanded_terms": ["减肥"],
        "retrieval_rounds": 1,
        "search_results": [
            {
                "perspective": "基础",
                "sub_dimension": "What",
                "query": "减脂是什么",
                "results": [
                    {"title": "减脂是什么？", "url": "https://www.zhihu.com/question/1"},
                    {"title": "到底减脂是什么？", "url": "https://www.zhihu.com/question/2"},
                    {"title": "究竟减脂是什么？", "url": "https://www.zhihu.com/question/3"},
                ],
            },
        ],
        "fetched_pages": {
            "https://www.zhihu.com/question/1": "<html><h1>减脂是什么？</h1></html>",
            "https://www.zhihu.com/question/2": "<html><h1>到底减脂是什么？</h1></html>",
            "https://www.zhihu.com/question/3": "<html><h1>究竟减脂是什么？</h1></html>",
        },
    }
    tmpdir = tempfile.mkdtemp()
    try:
        result = pipeline.run(manifest, tmpdir, is_abstract=False)
        assert result["confirmed_count"] >= 1

        with open(os.path.join(tmpdir, "problem_list.json"), "r", encoding="utf-8") as f:
            pl = json.load(f)
        confirmed = pl["problems"]
        assert len(confirmed) >= 1
        assert confirmed[0]["source_count"] == 3
        assert confirmed[0]["total_frequency"] == 3
    finally:
        shutil.rmtree(tmpdir)


def test_audit_includes_recommended_queries_for_missing_cells():
    """审计报告应为缺失格子包含下一轮推荐查询。"""
    manifest = {
        "topic": "减脂",
        "expanded_terms": ["减肥"],
        "retrieval_rounds": 1,
        "search_results": [
            {
                "perspective": "基础",
                "sub_dimension": "What",
                "query": "减脂是什么",
                "results": [
                    {"title": "减脂怎么吃？", "url": "https://example.com/1"},
                ],
            },
        ],
        "fetched_pages": {
            "https://example.com/1": "<html><h1>减脂怎么吃？</h1></html>",
        },
    }
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline.run(manifest, tmpdir, is_abstract=False)
        with open(os.path.join(tmpdir, "audit_report.json"), "r", encoding="utf-8") as f:
            audit = json.load(f)
        assert "recommended_queries" in audit
        assert len(audit["recommended_queries"]) > 0
        for q in audit["recommended_queries"]:
            assert "perspective" in q
            assert "sub_dimension" in q
            assert "query" in q
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_pipeline_run()
    test_pipeline_tracks_source_and_reachability_in_audit()
    test_cross_url_semantic_duplicate_aggregates_sources_to_confirmed()
    test_audit_includes_recommended_queries_for_missing_cells()
    print("test_pipeline OK")
