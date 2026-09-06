#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""coverage_matrix.py — 16 格覆盖度检查。"""

from collections import defaultdict


# 16 格子定义
PERSPECTIVES = {
    "基础": ["What", "Why", "Who", "When", "Where", "How", "How much"],
    "旅程": ["认知期", "准备期", "执行期", "瓶颈期", "维持期"],
    "人群场景": ["人群差异", "场景差异"],
    "争议时效": ["争议", "时效"],
}

# 抽象主题可豁免的格子
ABSTRACT_EXEMPT = {"基础": ["How much"], "争议时效": ["争议"]}


def build_matrix(problems):
    """根据问题列表统计每个格子的覆盖数。"""
    matrix = {p: {s: 0 for s in subs} for p, subs in PERSPECTIVES.items()}
    for p in problems:
        perspective = p.get("retrieval_perspective")
        sub = p.get("sub_dimension")
        if perspective in matrix and sub in matrix[perspective]:
            matrix[perspective][sub] += 1
    return matrix


def missing_cells(matrix, is_abstract=False):
    """返回缺失的格子列表。"""
    missing = []
    for perspective, subs in PERSPECTIVES.items():
        for sub in subs:
            if matrix[perspective].get(sub, 0) < 1:
                exempt = ABSTRACT_EXEMPT.get(perspective, []) if is_abstract else []
                if sub not in exempt:
                    missing.append((perspective, sub))
    return missing


def check(problems, is_abstract=False):
    """返回覆盖度检查结果。"""
    matrix = build_matrix(problems)
    missing = missing_cells(matrix, is_abstract=is_abstract)
    return {
        "matrix": matrix,
        "missing": missing,
        "fully_covered": len(missing) == 0,
        "is_abstract": is_abstract,
        "exempt": [f"{p}/{s}" for p, ss in ABSTRACT_EXEMPT.items() for s in ss] if is_abstract else [],
    }


def main():
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python3 coverage_matrix.py '<问题 JSON 数组>' [--abstract]")
        sys.exit(1)
    problems = json.loads(sys.argv[1])
    is_abstract = "--abstract" in sys.argv
    print(json.dumps(check(problems, is_abstract), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
