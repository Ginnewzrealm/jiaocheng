#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dedupe_questions.py — 问题去重：精确 + 语义 + 子集。

语义去重默认使用简化字符集合的 Jaccard 相似度；当 sentence-transformers 可用时
可替换为余弦相似度。
"""

import re
from collections import defaultdict


def normalize(text):
    """文本归一化：去首尾空格、统一问号、去除常见无意义助词。"""
    text = text.strip()
    text = text.replace("?", "？")
    # 去除语气词和重复问号
    text = re.sub(r"[吗呢么]+[？?]*$", "？", text)
    text = re.sub(r"[？?]+$", "？", text)
    return text.strip()


def char_set(text):
    """提取文本中的中文字符集合，用于 Jaccard 计算。"""
    return set(re.findall(r"[一-龥]", text))


def jaccard(a, b):
    sa, sb = char_set(a), char_set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def is_subset(short, long_):
    """判断 short 的问题是否是 long_ 的完整子集（按字符集合）。"""
    ss, ls = char_set(short), char_set(long_)
    if not ss:
        return False
    return ss <= ls and len(short) < len(long_)


class _UnionFind:
    """并查集，用于传递性语义合并。"""

    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py


def _similar(a, b, threshold):
    """判断两个问题是否语义相似或为子集关系。"""
    if jaccard(a, b) >= threshold:
        return True
    if is_subset(a, b) or is_subset(b, a):
        return True
    return False


def _merge_sources(kept_sources, candidate_sources):
    """将 candidate_sources 合并到 kept_sources 中，支持 dict 或 list 格式。"""
    if isinstance(kept_sources, dict):
        if isinstance(candidate_sources, dict):
            for url, freq in candidate_sources.items():
                kept_sources[url] = kept_sources.get(url, 0) + freq
        elif isinstance(candidate_sources, list):
            for s in candidate_sources:
                url = s.get("url")
                freq = s.get("frequency", 1)
                if url:
                    kept_sources[url] = kept_sources.get(url, 0) + freq
    elif isinstance(kept_sources, list):
        if isinstance(candidate_sources, dict):
            for url, freq in candidate_sources.items():
                existing = next((x for x in kept_sources if x.get("url") == url), None)
                if existing:
                    existing["frequency"] = existing.get("frequency", 0) + freq
                else:
                    kept_sources.append({"url": url, "frequency": freq})
        elif isinstance(candidate_sources, list):
            for s in candidate_sources:
                url = s.get("url")
                if not url:
                    continue
                existing = next((x for x in kept_sources if x.get("url") == url), None)
                if existing:
                    existing["frequency"] = existing.get("frequency", 0) + s.get("frequency", 1)
                else:
                    kept_sources.append(dict(s))


def dedupe(questions, semantic_threshold=0.85):
    """去重主函数。

    questions: list of dict, 每个 dict 至少包含 'text'
    返回：{
        unique: [dict],
        duplicates_merged: int,
        detail: [{kept, merged: [text...]}]
    }
    """
    # 1. 精确去重
    seen_texts = {}
    unique = []
    for q in questions:
        key = normalize(q.get("text", ""))
        if not key:
            continue
        if key in seen_texts:
            seen_texts[key].append(q)
        else:
            seen_texts[key] = [q]
            unique.append({**q, "_norm": key, "duplicates": [], "sources": q.get("sources", {})})

    n = len(unique)
    if n == 0:
        return {"unique": [], "duplicates_merged": 0, "detail": []}

    # 2. 语义去重 + 子集去重（并查集实现传递性合并）
    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if _similar(unique[i]["_norm"], unique[j]["_norm"], semantic_threshold):
                uf.union(i, j)

    # 3. 按组聚合：保留最长文本，合并来源和 duplicates
    groups = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)

    result = []
    detail = []
    duplicates_merged = 0
    for indices in groups.values():
        # 按长度降序，优先保留更长/更具体的问题
        indices_sorted = sorted(indices, key=lambda i: len(unique[i]["_norm"]), reverse=True)
        kept = unique[indices_sorted[0]]
        merged_indices = indices_sorted[1:]
        duplicates_merged += len(merged_indices)

        merged_texts = []
        for idx in merged_indices:
            candidate = unique[idx]
            merged_texts.append(candidate.get("text", candidate["_norm"]))
            kept["duplicates"].append(candidate.get("text", candidate["_norm"]))
            # 合并来源频次
            _merge_sources(kept.get("sources", {}), candidate.get("sources", {}))

        detail.append({
            "kept": kept.get("text", kept["_norm"]),
            "merged": merged_texts,
        })
        result.append(kept)

    # 移除内部使用的 _norm
    for r in result:
        r.pop("_norm", None)

    return {
        "unique": result,
        "duplicates_merged": duplicates_merged,
        "detail": detail,
    }


def main():
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python3 dedupe_questions.py '<json数组>'")
        print('示例: python3 dedupe_questions.py \'["减脂是什么？", "什么是减脂？", "减脂"]\'')
        sys.exit(1)
    try:
        arr = json.loads(sys.argv[1])
    except Exception:
        arr = [sys.argv[1]]
    questions = [{"text": t} for t in arr]
    out = dedupe(questions)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
