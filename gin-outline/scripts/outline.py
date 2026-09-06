#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-outline v2 工具脚本：缺口判定 / 单篇大纲机检。

v2（2026-09-06，一题一文改造）规则全部对 references/outline-methodology.md 条目：
§6 素材存在性 / 卡片真实且达标 / 每节≥1证据   → ❌
§2 每节必须有"干什么"施工说明                  → ❌
§3 定义式标题 ❌；术语词收尾标题 ⚠️（人话化）
§1 写给具体画像 ❌ / 读完能须"能"字+真动作 ❌ / 节数5-8 ⚠️
v1 多章格式守卫：拒绝并指路模板               → ❌

check_outline 返回 {"errors": [...], "warnings": [...]}（空 = 通过）。
"""
import argparse
import json
import os
import re


# ---------- 缺口判定 ----------

def _shingles(topic, n=2):
    """主题词拆 n-字 shingles：'减脂平台期' → {减脂, 脂平, 平台, 台期}"""
    return {topic[i:i + n] for i in range(len(topic) - n + 1)}


def _cards(manifest):
    return manifest.get("达标卡") or manifest.get("cards") or []


def _q_of(p):
    return p.get("问题") or p.get("text") or ""


def find_gaps(manifest, problems, topic, min_overlap=2):
    """缺口 = 问题清单里与主题相关、但答案卡库没有覆盖的问题。

    相关性判定：问题与主题共享 ≥2 个 shingles（'平台期持续多久'命中
    平台/台期 = 2 → 相关；'减脂和减肥区别'只命中减脂 = 1 → 无关）。
    """
    if isinstance(problems, dict):
        problems = (problems.get("problems") or problems.get("items")
                    or problems.get("问题清单") or [])
    sh = _shingles(topic)
    # 两字主题只有一个 shingle，阈值降到 1；长主题仍要求 ≥2
    threshold = min(min_overlap, len(sh))
    covered = {c.get("问题", "") for c in _cards(manifest)}
    gaps = []
    for p in problems:
        q = _q_of(p)
        if not q:
            continue
        score = len(sh & _shingles(q, 2))
        if score < threshold and len(q) >= 3:
            if any(q[i:i + 3] in topic for i in range(len(q) - 2)):
                score = threshold
        if score >= threshold and q not in covered:
            gaps.append({"问题": q, "频次": p.get("频次") or p.get(
                "total_frequency", 0), "说明": "与主题相关但无答案卡覆盖"})
    return {"缺口": gaps}


# ---------- 机检词表 ----------

_KNOWLEDGE_AFTER_NENG = re.compile(r"^[能会](了解|理解|知道|认识|掌握|学习)(?!到)")
_DEFINITION_TITLE = re.compile(r"^(什么是|什么叫|何谓|聊聊)")
_DEFINITION_TAIL = re.compile(r"(的定义|的概念|是什么|是什么意思)$")
_TERM_ENDINGS = ("档位", "杠杆", "映射", "拓扑", "范式", "矩阵", "体系",
                 "机制", "原理", "流程", "策略", "模型", "框架")
_GENERIC_READERS = {"新手", "初学者", "小白", "入门用户", "零基础", ""}


# ---------- 机检 ----------

def check_outline(o, manifest, library=None):
    """单篇大纲机检。返回 {"errors": [...], "warnings": [...]}。"""
    errors, warnings = [], []

    # v1 多章格式守卫
    if "章节" in o or "小节" not in o:
        errors.append("❌ v1 多章大纲格式已废止——一题一文，标准格式见 "
                      "references/output-templates.md")
        return {"errors": errors, "warnings": warnings}

    card_pool = {c.get("问题", ""): c for c in _cards(manifest)}

    # §6 卡片真实且达标（达标卡才许施工）
    q = o.get("问题", "")
    card = card_pool.get(q)
    if card is None:
        errors.append(f"❌ 卡片不在答案卡库：{q}")
    elif card.get("状态") != "达标":
        errors.append(f"❌ 卡片未达标（状态={card.get('状态')}）：{q}"
                      f"——先回 gin-answer 补采到达标再排大纲")

    # §1 写给/读完能
    xg = (o.get("写给") or "").strip()
    if xg in _GENERIC_READERS:
        errors.append("❌ 写给缺失或太泛（'新手'不算数）——写一句具体画像："
                      "他现在会什么、卡在哪")
    dn = (o.get("读完能") or "").strip()
    if not dn:
        errors.append("❌ 读完能缺失——'能'字头的可检验动作（§1 三决策）")
    elif not re.match(r"^[能会]", dn):
        errors.append(f"❌ 读完能须以'能'开头：{dn}")
    elif _KNOWLEDGE_AFTER_NENG.match(dn):
        errors.append(f"❌ 读完能是知识动词伪装：{dn}——'了解/理解'不可测，"
                      f"改成真动作（能算出/能判断/能拆穿）")

    sections = o.get("小节") or []

    # §1 节数
    if not (5 <= len(sections) <= 8):
        warnings.append(f"⚠️ 节数 {len(sections)} 超出 5–8 区间——"
                        f"过少内容单薄，过多被切碎（§1 三决策）")

    for i, sec in enumerate(sections, 1):
        name = sec.get("标题", f"第{i}节")

        # §2 施工说明必填
        if not (sec.get("干什么") or "").strip():
            errors.append(f"❌ [第{i}节] 缺'干什么'施工说明——空标题不许进目录"
                          f"（§2：写不出这一幕演什么 = 该节不存在，删）")

        # §6 每节 ≥1 证据
        if not sec.get("证据"):
            errors.append(f"❌ [第{i}节] 每节至少挂 1 条卡片证据（§6）")

        # §3/§4 标题：定义式 ❌；术语词收尾 ⚠️
        t = (sec.get("标题") or "").strip()
        if t and (_DEFINITION_TITLE.match(t) or _DEFINITION_TAIL.search(t)):
            errors.append(f"❌ [第{i}节] 定义式标题：{t}——开头必须具体场景，"
                          f"不是概念定义（§4.1 读者先来后理）")
        elif t and t.endswith(_TERM_ENDINGS):
            warnings.append(f"⚠️ [第{i}节] 标题以术语词收尾：{t}——真人不会"
                            f"这么念，术语进'干什么'列（§3 标题人话化）")

    # §6 素材存在且是文件
    if library:
        for mat in o.get("素材") or []:
            p = os.path.join(library, mat)
            if not os.path.exists(p):
                errors.append(f"❌ 素材不存在：{mat}")
            elif not os.path.isfile(p):
                errors.append(f"❌ 素材不是文件：{mat}（写目录路径凑数不行）")

    return {"errors": errors, "warnings": warnings}


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="gin-outline 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gaps", help="判定缺口（主题相关但无卡覆盖的问题）")
    g.add_argument("--manifest", required=True)
    g.add_argument("--problems", required=True)
    g.add_argument("--topic", required=True)

    c = sub.add_parser("check", help="机检单篇大纲")
    c.add_argument("--outline", required=True)
    c.add_argument("--manifest", required=True)
    c.add_argument("--library", default=None)

    args = ap.parse_args()

    if args.cmd == "gaps":
        manifest = json.load(open(args.manifest, encoding="utf-8"))
        problems = json.load(open(args.problems, encoding="utf-8"))
        if isinstance(problems, dict):
            problems = (problems.get("problems") or problems.get("items")
                        or problems.get("问题清单") or [])
        print(json.dumps(find_gaps(manifest, problems, args.topic),
                         ensure_ascii=False, indent=1))
    elif args.cmd == "check":
        o = json.load(open(args.outline, encoding="utf-8"))
        manifest = json.load(open(args.manifest, encoding="utf-8"))
        r = check_outline(o, manifest, args.library)
        print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
