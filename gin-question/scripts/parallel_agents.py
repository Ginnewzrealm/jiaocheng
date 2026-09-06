#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parallel_agents.py — 4 视角检索 Agent 的协调逻辑。

本模块不直接 spawn 子进程/子 Agent，而是生成每个视角需要执行的检索词列表
和检查清单，供上层（Claude 或 pipeline）调度。
"""

from common import read_reference


PERSPECTIVES = {
    "基础": {
        "What": "{扩展词} 是什么 / 定义 / 什么意思",
        "Why": "{扩展词} 为什么 / 原理 / 原因",
        "Who": "{扩展词} 适合谁 / 人群 / 谁需要",
        "When": "{扩展词} 什么时候 / 多久 / 最佳时机",
        "Where": "{扩展词} 哪里 / 场景 / 在什么地方",
        "How": "{扩展词} 怎么做 / 步骤 / 方法",
        "How much": "{扩展词} 多少 / 标准 / 剂量 / 成本",
    },
    "旅程": {
        "认知期": "{扩展词} 新手 入门 是什么 值得吗",
        "准备期": "{扩展词} 准备 需要 第一次 怎么开始",
        "执行期": "{扩展词} 怎么做 方法 步骤 频率",
        "瓶颈期": "{扩展词} 平台期 出错 受伤 怎么办 没效果",
        "维持期": "{扩展词} 维持 保持 不反弹 进阶",
    },
    "人群场景": {
        "人群差异": "{人群} {扩展词} 注意",
        "场景差异": "{扩展词} 出差 旅行 怎么办",
    },
    "争议时效": {
        "争议": "{扩展词} 争议",
        "时效": "{扩展词} 2025 最新",
    },
}

PEOPLE_POOL = [
    "女性", "男性", "青少年", "老人", "孕妇", "哺乳期",
    "糖尿病", "高血压", "甲状腺", "高血脂", "运动员",
    "健身爱好者", "体力劳动者",
]


def build_search_terms(topic, expanded_terms, perspective=None):
    """生成指定视角的检索词列表。

    返回：[(perspective, sub_dimension, search_term), ...]
    """
    terms = [topic] + list(expanded_terms)
    results = []
    perspectives = [perspective] if perspective else PERSPECTIVES.keys()

    for per in perspectives:
        for sub, template in PERSPECTIVES[per].items():
            if per == "人群场景" and sub == "人群差异":
                for person in PEOPLE_POOL:
                    for t in terms[:3]:  # 人群差异只取前几个扩展词避免爆炸
                        term = template.replace("{人群}", person).replace("{扩展词}", t)
                        results.append((per, sub, term))
            else:
                for t in terms[:5]:  # 每个子维度取前 5 个扩展词
                    term = template.replace("{扩展词}", t)
                    results.append((per, sub, term))
    return results


def agent_manifest(topic, expanded_terms):
    """生成 4 个 Agent 的任务清单。"""
    return {
        per: build_search_terms(topic, expanded_terms, perspective=per)
        for per in PERSPECTIVES.keys()
    }


def main():
    import sys
    import json
    if len(sys.argv) < 2:
        print("用法: python3 parallel_agents.py '<topic>' '[扩展词1, 扩展词2]'")
        sys.exit(1)
    topic = sys.argv[1]
    expanded = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
    print(json.dumps(agent_manifest(topic, expanded), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
