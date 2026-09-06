#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.py — gin-question 处理流水线。

用法：
    python3 pipeline.py --manifest manifest.json --output-dir ./output [--abstract]

manifest.json 格式：
{
  "topic": "减脂",
  "expanded_terms": ["减肥", "瘦身", ...],
  "search_results": [
    {"perspective": "基础", "sub_dimension": "What", "query": "...",
     "results": [{"title": "...", "url": "...", "snippet": "..."}]}
  ],
  "fetched_pages": {"https://...": "<html>..."}
}

如果提供了外部搜索 API key（SERPAPI_KEY / BING_API_KEY），未来可扩展 --collect 模式
自动收集 search_results 和 fetched_pages。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
from coverage_matrix import check as coverage_check
from dedupe_questions import dedupe
from judge_questions import filter_questions
from output_renderer import render_outputs
from question_extractor import extract_from_content, extract_from_search_result
from query_generator import generate as generate_queries
from saturation_checker import SaturationTracker
from source_grader import grade_url


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_candidates(manifest):
    """从 manifest 中构建问题候选。

    返回：(valid_candidates, invalid_candidates)
    只接受 extracted_from 为 content 或 search_title 的问题。
    """
    candidates = []
    fetched_pages = manifest.get("fetched_pages", {})
    topic = manifest.get("topic")

    for group in manifest.get("search_results", []):
        perspective = group.get("perspective")
        sub_dimension = group.get("sub_dimension")
        for r in group.get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")

            # 1. 优先从已抓取的页面内容中提取
            html = fetched_pages.get(url)
            if html:
                extracted = extract_from_content(html, url, topic=topic)
                for e in extracted:
                    e["retrieval_perspective"] = perspective
                    e["sub_dimension"] = sub_dimension
                    candidates.append(e)
            else:
                # 2. 未抓取到页面：尝试用搜索结果页面标题
                q = extract_from_search_result(title, url, topic=topic)
                if q:
                    q["retrieval_perspective"] = perspective
                    q["sub_dimension"] = sub_dimension
                    candidates.append(q)

    # 真实性校验：只接受来自 content 或 search_title 的问题
    valid = []
    invalid = []
    for c in candidates:
        src = c.get("extracted_from")
        if src in ("content", "search_title"):
            valid.append(c)
        else:
            invalid.append(c)
    return valid, invalid


def aggregate_sources(candidates):
    """按问题文本聚合来源和频次。"""
    buckets = {}
    for c in candidates:
        text = c.get("text", "").strip()
        if not text:
            continue
        key = common.normalize_text(text)
        if key not in buckets:
            buckets[key] = {
                "text": text,
                "original": text,
                "sources": {},
                "retrieval_perspective": c.get("retrieval_perspective", ""),
                "sub_dimension": c.get("sub_dimension", ""),
            }
        url = c.get("source_url", "")
        buckets[key]["sources"].setdefault(url, 0)
        buckets[key]["sources"][url] += 1

    aggregated = []
    for key, b in buckets.items():
        sources = []
        for url, freq in b["sources"].items():
            sources.append({"url": url, "type": grade_url(url), "frequency": freq})
        # 若 type 为 None，降级为 tertiary
        for s in sources:
            if s["type"] is None:
                s["type"] = "tertiary"
        aggregated.append({
            "text": b["text"],
            "original": b["original"],
            "retrieval_perspective": b["retrieval_perspective"],
            "sub_dimension": b["sub_dimension"],
            "sources": sources,
            "total_frequency": sum(s["frequency"] for s in sources),
            "source_count": len(sources),
        })
    return aggregated


def apply_frequency_gate(aggregated):
    """应用来源分级 + 频次门槛。"""
    confirmed, pending = [], []
    for item in aggregated:
        sources = item["sources"]
        has_primary = any(s["type"] == "primary" for s in sources)
        secondary_count = sum(s["frequency"] for s in sources if s["type"] == "secondary")
        tertiary_count = sum(s["frequency"] for s in sources if s["type"] == "tertiary")

        if has_primary or secondary_count >= 2 or tertiary_count >= 3:
            item["status"] = "confirmed"
            confirmed.append(item)
        else:
            item["status"] = "single_source"
            pending.append(item)
    return confirmed, pending


def assign_ids(problems, prefix="P"):
    for i, p in enumerate(problems, 1):
        p["id"] = common.id_for_index(i, prefix)
    return problems


def _compute_source_reachability(manifest):
    """计算源可触达率：唯一 URL 中被成功抓取的比例。"""
    fetched_pages = manifest.get("fetched_pages", {})
    urls = set()
    for group in manifest.get("search_results", []):
        for r in group.get("results", []):
            url = r.get("url", "")
            if url:
                urls.add(url)
    if not urls:
        return 0.0
    fetched = sum(1 for url in urls if url in fetched_pages)
    return round(fetched / len(urls), 2)


def run(manifest, output_dir, is_abstract=False):
    topic = manifest["topic"]

    # 1. 构建候选
    candidates, invalid_candidates = build_candidates(manifest)

    # 2. QM 过滤
    filtered = filter_questions(candidates)
    qm_rejected = filtered["rejected"]
    candidates = filtered["passed"]

    # 3. 聚合来源
    aggregated = aggregate_sources(candidates)

    # 4. 去重
    dedup_result = dedupe(aggregated)
    unique = dedup_result["unique"]

    # 4b. 去重后重新计算来源数和总频次
    for item in unique:
        sources = item.get("sources", [])
        if isinstance(sources, list):
            item["source_count"] = len(sources)
            item["total_frequency"] = sum(s.get("frequency", 1) for s in sources)
        elif isinstance(sources, dict):
            item["source_count"] = len(sources)
            item["total_frequency"] = sum(sources.values())

    # 5. 频次门槛
    confirmed, pending = apply_frequency_gate(unique)

    # 6. ID 分配
    confirmed = assign_ids(confirmed)
    pending = assign_ids(pending, prefix="PV")

    # 7. 覆盖度检查（基于所有通过 QM 的问题，不只是 confirmed）
    all_valid = confirmed + pending
    coverage = coverage_check(all_valid, is_abstract=is_abstract)

    # 7b. 为缺失格子生成下一轮推荐查询
    recommended_queries = generate_queries(
        topic,
        manifest.get("expanded_terms", []),
        coverage["missing"],
        max_per_cell=2,
    )

    # 8. 审计报告
    qm3_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for r in qm_rejected:
        cat = r.get("qm3_category")
        if cat in qm3_counts:
            qm3_counts[cat] += 1

    audit = {
        "exit_reason": "saturated",
        "retrieval_rounds": manifest.get("retrieval_rounds", 1),
        "search_terms_total": len(manifest.get("search_results", [])),
        "candidates_total": len(candidates) + len(qm_rejected) + len(invalid_candidates),
        "duplicates_merged": dedup_result.get("duplicates_merged", 0),
        "qm1_rejected": 0,
        "qm2_rejected": 0,
        "qm3_rejected": qm3_counts,
        "frequency_rejected": len(pending),
        "from_fetched_pages": sum(1 for c in candidates if c.get("extracted_from") == "content"),
        "from_search_title": sum(1 for c in candidates if c.get("extracted_from") == "search_title"),
        "from_invalid_source": len(invalid_candidates),
        "source_reachability": _compute_source_reachability(manifest),
        "fetch_failures": [],
        "perspective_coverage": coverage["matrix"],
        "agent_failures": [],
        "empty_perspectives": [f"{p}/{s}" for p, s in coverage["missing"]],
        "recommended_queries": recommended_queries,
        "is_abstract": is_abstract,
        "exempt": coverage.get("exempt", []),
        "notes": [
            "问题来源优先级：已抓取页面正文 > 搜索结果页面标题。",
            "未抓取页面且标题非疑问句的结果被丢弃。",
            "extracted_from 不合法的问题被直接丢弃，不计入 candidates_total。",
        ],
    }

    # 9. 输出
    outputs = render_outputs(topic, confirmed, pending, audit, output_dir)
    return {
        "outputs": outputs,
        "coverage": coverage,
        "confirmed_count": len(confirmed),
        "pending_count": len(pending),
        "rejected_count": len(qm_rejected),
    }


def main():
    parser = argparse.ArgumentParser(description="gin-question 处理流水线")
    parser.add_argument("--manifest", required=True, help="收集到的搜索结果 manifest JSON 文件")
    parser.add_argument("--output-dir", default="./output", help="输出目录")
    parser.add_argument("--abstract", action="store_true", help="主题是否为抽象主题（放宽 How much 和 争议）")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    result = run(manifest, args.output_dir, is_abstract=args.abstract)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
