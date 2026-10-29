#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""query_generator.py — 根据覆盖度缺失格子生成下一轮搜索查询。

输入：主题、扩展词、缺失格子列表
输出：[(perspective, sub_dimension, query), ...]
"""


PERSPECTIVES = {
    "基础": {
        "What": ["{扩展词} 是什么", "{扩展词} 什么意思", "{扩展词} 定义"],
        "Why": ["{扩展词} 为什么", "{扩展词} 原理", "{扩展词} 原因"],
        "Who": ["{扩展词} 适合谁", "{扩展词} 人群", "{扩展词} 谁需要"],
        "When": ["{扩展词} 什么时候", "{扩展词} 多久", "{扩展词} 最佳时机"],
        "Where": ["{扩展词} 哪里", "{扩展词} 场景", "{扩展词} 在什么地方"],
        "How": ["{扩展词} 怎么做", "{扩展词} 步骤", "{扩展词} 方法"],
        "How much": ["{扩展词} 多少", "{扩展词} 标准", "{扩展词} 剂量"],
    },
    "旅程": {
        "认知期": ["{扩展词} 新手 入门", "{扩展词} 是什么 值得吗"],
        "准备期": ["{扩展词} 准备", "{扩展词} 第一次 怎么开始", "{扩展词} 入门准备"],
        "执行期": ["{扩展词} 怎么做", "{扩展词} 方法 步骤", "{扩展词} 频率"],
        "瓶颈期": ["{扩展词} 平台期", "{扩展词} 出错 怎么办", "{扩展词} 没效果"],
        "维持期": ["{扩展词} 维持", "{扩展词} 保持 不反弹", "{扩展词} 进阶"],
    },
    "人群场景": {
        "人群差异": ["{人群} {扩展词} 注意", "{人群} {扩展词} 适合吗"],
        "场景差异": ["{扩展词} 出差 旅行", "{扩展词} 场景"],
    },
    "争议时效": {
        "争议": ["{扩展词} 争议", "{扩展词} 误区", "{扩展词} 骗局"],
        "时效": ["{扩展词} 2026 最新", "{扩展词} 趋势", "{扩展词} 变化"],
    },
}

HEALTH_PEOPLE = [
    "女性", "男性", "青少年", "老人", "孕妇",
    "糖尿病", "高血压", "甲状腺", "高血脂", "运动员",
]
PEOPLE_POOL = ['初学者', '有经验的使用者', '维护人员']


def templates_for(profile='general'):
    from copy import deepcopy
    from datetime import date
    if profile not in ('general', 'health'):
        raise ValueError('domain_profile 必须为 general/health')
    templates = deepcopy(PERSPECTIVES)
    templates['争议时效']['时效'][0] = '{扩展词} ' + str(date.today().year) + ' 最新'
    if profile == 'general':
        templates['基础']['How much'] = ['{扩展词} 成本', '{扩展词} 数量', '{扩展词} 标准']
        templates['旅程']['瓶颈期'] = ['{扩展词} 常见错误', '{扩展词} 出错 怎么办', '{扩展词} 没效果']
        templates['旅程']['维持期'] = ['{扩展词} 维护', '{扩展词} 更新', '{扩展词} 进阶']
        templates['人群场景']['场景差异'] = ['{扩展词} 不同环境', '{扩展词} 使用场景']
    return templates


def generate(topic, expanded_terms, missing_cells, max_per_cell=3, profile='general'):
    """根据缺失格子生成下一轮搜索查询。

    missing_cells: [(perspective, sub_dimension), ...]
    返回：[{"perspective": ..., "sub_dimension": ..., "query": ...}, ...]
    """
    terms = [topic] + list(expanded_terms or [])
    queries = []
    seen = set()
    if max_per_cell < 1:
        raise ValueError('max_per_cell 必须大于 0')
    catalog = templates_for(profile)

    # 去重缺失格子，避免同一格子重复生成
    seen_cells = set()
    unique_missing = []
    for cell in missing_cells:
        key_cell = (cell[0], cell[1]) if isinstance(cell, (list, tuple)) else cell
        if key_cell not in seen_cells:
            seen_cells.add(key_cell)
            unique_missing.append(cell)

    for perspective, sub_dimension in unique_missing:
        templates = catalog.get(perspective, {}).get(sub_dimension, [])
        if not templates:
            continue

        count = 0
        if perspective == "人群场景" and sub_dimension == "人群差异":
            for person in (HEALTH_PEOPLE if profile == 'health' else PEOPLE_POOL):
                for term in terms[:3]:
                    for template in templates:
                        query = template.replace("{人群}", person).replace("{扩展词}", term)
                        key = (perspective, sub_dimension, query)
                        if key not in seen:
                            seen.add(key)
                            queries.append({
                                "perspective": perspective,
                                "sub_dimension": sub_dimension,
                                "query": query,
                            })
                            count += 1
                            if count >= max_per_cell:
                                break
                    if count >= max_per_cell:
                        break
                if count >= max_per_cell:
                    break
        else:
            for term in terms[:5]:
                for template in templates:
                    query = template.replace("{扩展词}", term).replace("{人群}", "")
                    key = (perspective, sub_dimension, query)
                    if key not in seen:
                        seen.add(key)
                        queries.append({
                            "perspective": perspective,
                            "sub_dimension": sub_dimension,
                            "query": query,
                        })
                        count += 1
                        if count >= max_per_cell:
                            break
                if count >= max_per_cell:
                    break

    return queries


def main():
    import sys
    import json
    if len(sys.argv) < 4:
        print("用法: python3 query_generator.py '<topic>' '[扩展词]' '[[perspective, sub], ...]'")
        sys.exit(1)
    topic = sys.argv[1]
    expanded = json.loads(sys.argv[2])
    missing = json.loads(sys.argv[3])
    queries = generate(topic, expanded, missing)
    print(json.dumps(queries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
