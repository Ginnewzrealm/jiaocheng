#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seed_expander.py — 从搜索结果中提取主题扩展词。

输入：搜索结果的标题/摘要文本列表
输出：扩展词列表（只返回出现在输入中的词）
"""

import re


# 常见同义词/别称提示词，用于从文本中识别扩展词
SEED_HINTS = ["又称", "也叫", "亦称", "别称", "同义词", "简称", "俗称", "黑话", "术语"]


def extract_terms(text, topic):
    """从文本中提取可能与主题相关的扩展词。

    简单实现：按标点切分，找出包含主题相关字的短语。
    更精确的实现应使用 LLM，但本脚本保持零依赖。
    """
    # 尝试在提示词附近提取
    for hint in SEED_HINTS:
        pattern = re.compile(r"[^，。；！？\n]{0,20}" + re.escape(hint) + r"[^，。；！？\n]{0,60}")
        for match in pattern.findall(text):
            parts = re.split(r"[、，；/]", match)
            for p in parts:
                p = p.strip()
                if p and p != topic and len(p) >= 2:
                    yield p


def expand(topic, search_results, max_terms=10):
    """从搜索结果中提取扩展词。

    search_results: list of dict with 'title', 'snippet'
    """
    candidates = []
    for r in search_results:
        text = f"{r.get('title', '')} {r.get('snippet', '')}"
        for term in extract_terms(text, topic):
            if term not in candidates:
                candidates.append(term)
        if len(candidates) >= max_terms * 2:
            break
    return candidates[:max_terms]


def main():
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python3 seed_expander.py '<topic>' '<search-results-json>'")
        sys.exit(1)
    topic = sys.argv[1]
    results = json.loads(sys.argv[2])
    print(json.dumps(expand(topic, results), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
