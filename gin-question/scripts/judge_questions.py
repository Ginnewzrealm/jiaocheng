#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judge_questions.py — QM1-QM3 问题过滤。

输入：问题文本 + 来源信息
输出：{passed: bool, qm3_category: str|None, reason: str}
"""

import re


# QM3-D: 不可证伪类主观词
SUBJECTIVE_WORDS = {
    "好不好", "值不值得", "应不应该", "该不该", "喜不喜欢", "想不想",
    "划不划算", "有没有意义", "美不美", "帅不帅", "香不香",
}

# QM3-D: 未来预测词
FUTURE_WORDS = {
    "未来会不会", "以后会怎么样", "将来", "前景", "趋势如何", "会不会火",
}

# QM3-C: 过度抽象词
ABSTRACT_WORDS = {
    "人生", "世界", "一切", "永远", "意义", "命运", "宇宙", "终极",
}

# QM3-A/C: AI 倒推痕迹
AI_HINTS = {
    "可能有人问", "有人好奇", "假设你问", "假设有人问", "我们可能会问",
    "一个常见的问题是", "很多人会问",
}

# QM3-B: 修辞/情绪/命令
RHETORICAL_PATTERNS = [
    r"这还用说吗",
    r"难道不",
    r"难道不是",
    r"你为什么不",
    r"你难道不",
    r"特么",
    r"他妈",
    r"坑爹",
    r"何异于",
    r"不夸张地",
    r"看起来好像",
    r"听起来好像",
    r"你不觉得",
    r"谁不知道",
    r"谁会",
    r"还不简单",
    r"明摆着",
    r"还不是",
    r"难道不正是",
    r"不是在说",
    r"教你",            # 「教你辨真假」
    r"怎么辨别",
    r"怎么分辨",
]


def _has_any(text, words):
    return any(w in text for w in words)


def _has_pattern(text, patterns):
    return any(re.search(p, text) for p in patterns)


def judge(text, source_url=None):
    """对单个问题进行 QM1-QM3 判定。

    返回 dict:
        passed: bool
        qm3_category: None | 'A' | 'B' | 'C' | 'D' | 'E'
        reason: str
    """
    text = text.strip()

    # QM1: 来源真实 + 疑问句式
    if not source_url:
        return {"passed": False, "qm3_category": "E", "reason": "缺少来源 URL，不满足 QM1"}

    if len(text) < 5:
        return {"passed": False, "qm3_category": "C", "reason": "文本过短（<5 字），不满足 QM1"}

    # 疑问句式检查
    if not (text.endswith("？") or text.endswith("?") or _has_any(text, {"吗", "呢", "么", "怎么", "什么", "为什么", "为何", "多少", "哪些", "哪个", "是不是", "能不能", "可不可以", "如何", "哪里", "何时", "谁"})):
        return {"passed": False, "qm3_category": "E", "reason": "非疑问句式，不满足 QM1"}

    # 感叹号结尾但不是疑问句：判定为陈述/感叹 (QM3-B)
    if (text.endswith("！") or text.endswith("!")) and not (text.endswith("？") or text.endswith("?")):
        return {"passed": False, "qm3_category": "B", "reason": "以感叹号结尾，多为感叹/修辞，QM3-B"}

    # QM3-A: 虚构类 / AI 倒推
    if _has_any(text, AI_HINTS):
        return {"passed": False, "qm3_category": "A", "reason": "含 AI 倒推痕迹，QM3-A"}

    # QM3-B: 修辞/情绪/命令
    if _has_pattern(text, RHETORICAL_PATTERNS):
        return {"passed": False, "qm3_category": "B", "reason": "含修辞反问或情绪宣泄，QM3-B"}
    if text.startswith("你为什么不") or text.startswith("你为什么不"):
        return {"passed": False, "qm3_category": "B", "reason": "命令/建议句式，QM3-B"}

    # QM3-C: 无真实意图
    if _has_any(text, ABSTRACT_WORDS):
        return {"passed": False, "qm3_category": "C", "reason": "含过度抽象词，QM3-C"}

    # 检查残缺：缺少主语/谓语/宾语 —— 简化判定：纯短词
    if re.fullmatch(r"[一-龥]{1,3}[吗呢？?]", text):
        return {"passed": False, "qm3_category": "E", "reason": "无效二元/过短问题，QM3-E"}

    # QM3-D: 不可证伪
    if _has_any(text, SUBJECTIVE_WORDS):
        return {"passed": False, "qm3_category": "D", "reason": "含主观价值词，QM3-D"}
    if _has_any(text, FUTURE_WORDS):
        return {"passed": False, "qm3_category": "D", "reason": "含未来预测词，QM3-D"}

    return {"passed": True, "qm3_category": None, "reason": "通过 QM1-QM3"}


def filter_questions(questions):
    """批量过滤问题。

    questions: list of dict with keys 'text', 'source_url'
    返回：{passed: [dict], rejected: [dict]}
    """
    passed, rejected = [], []
    for q in questions:
        result = judge(q.get("text", ""), q.get("source_url"))
        q.update(result)
        if result["passed"]:
            passed.append(q)
        else:
            rejected.append(q)
    return {"passed": passed, "rejected": rejected}


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 judge_questions.py '问题文本' [source_url]")
        sys.exit(1)
    text = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "https://example.com"
    print(judge(text, url))


if __name__ == "__main__":
    main()
