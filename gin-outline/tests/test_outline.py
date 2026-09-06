#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-outline v2 回归测试——一题一文 + 目录表 + 人话标题。

每条规则对 references/outline-methodology.md 一个条目：
§6 素材存在/卡片真实/每节证据；§2 每节干什么；§3 标题人话化；
§1 三决策（写给/读完能/节数）；§4 开头非概念；§5 卡片达标才许施工。
运行：python3 -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import outline  # noqa: E402


@pytest.fixture
def env(tmp_path):
    lib = tmp_path / "lib"
    for d in ["L1", "L3", "L7_研究补充"]:
        (lib / d).mkdir(parents=True)
    (lib / "L3" / "底层逻辑.md").write_text("x", encoding="utf-8")
    manifest = {
        "观察哨": [],
        "达标卡": [
            {"问题": "减肥时热量缺口标准是多少", "类型": "方法型", "状态": "达标",
             "置信度": "高", "一句话答案": "每日300-500大卡",
             "出处": [{"来源": "L3/底层逻辑.md", "定级": "high"}]},
            {"问题": "减重10斤跟减脂10斤的区别", "类型": "事实型", "状态": "达标",
             "置信度": "高", "一句话答案": "减重≠减脂",
             "出处": [{"来源": "L3/底层逻辑.md", "定级": "high"}]},
        ],
    }
    mf = tmp_path / "answers-manifest.json"
    mf.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return {"dir": tmp_path, "manifest": mf, "lib": lib}


def _article(**over):
    """v2 合法单篇大纲（6 节，人话标题）。"""
    o = {
        "问题": "减肥时热量缺口标准是多少",
        "标题": "减肥时热量缺口，到底该留多少？",
        "类型": "方法型",
        "写给": "打算开始控制饮食、但从没算过账的减肥者",
        "读完能": "能算出自己的TDEE并设定每日300-500大卡缺口",
        "小节": [
            {"节": 1, "标题": "先算一笔身体的账",
             "干什么": "小张3斤得而复失开场，引出要算账", "证据": ["一句话答案"]},
            {"节": 2, "标题": "你一天到底消耗多少",
             "干什么": "TDEE三构成+活动系数，算出读者自己的数", "证据": ["出处"]},
            {"节": 3, "标题": "选多大的缺口才合适",
             "干什么": "三档对照，标准答案300-500", "证据": ["出处"]},
            {"节": 4, "标题": "别减掉肌肉",
             "干什么": "蛋白质+力量训练两杠杆", "证据": ["出处"]},
            {"节": 5, "标题": "填出你的缺口计算器",
             "干什么": "动手填模板", "证据": ["一句话答案"]},
            {"节": 6, "标题": "回到小张那2斤反弹",
             "干什么": "拆解水分回流+没纪律，回收开头", "证据": ["一句话答案"]},
        ],
        "素材": ["L3/底层逻辑.md"],
        "未采用": {},
    }
    o.update(over)
    return o


def _run(env, o):
    return outline.check_outline(o, json.loads(env["manifest"].read_text(
        encoding="utf-8")), str(env["lib"]))


# ---------- 合法基线 ----------

def test_valid_article_passes(env):
    r = _run(env, _article())
    assert r["errors"] == [] and r["warnings"] == []


# ---------- §6 素材/卡片/证据 ----------

def test_ghost_material_flagged(env):
    o = _article(素材=["L3/不存在的文件.md"])
    assert any("素材" in e for e in _run(env, o)["errors"])


def test_material_dir_not_file_flagged(env):
    o = _article(素材=["L3"])
    assert any("素材" in e for e in _run(env, o)["errors"])


def test_ghost_card_flagged(env):
    o = _article(问题="库里没有的问题")
    assert any("卡片" in e or "问题" in e for e in _run(env, o)["errors"])


def test_card_not_up_to_standard_flagged(env):
    m = json.loads(env["manifest"].read_text(encoding="utf-8"))
    m["达标卡"][0]["状态"] = "待补采"
    r = outline.check_outline(_article(), m, str(env["lib"]))
    assert any("达标" in e for e in r["errors"])


def test_section_without_evidence_flagged(env):
    o = _article()
    o["小节"][2]["证据"] = []
    assert any("证据" in e for e in _run(env, o)["errors"])


# ---------- §2 每节必须有施工说明 ----------

def test_section_missing_ganshenme_flagged(env):
    o = _article()
    o["小节"][1]["干什么"] = "  "
    assert any("干什么" in e for e in _run(env, o)["errors"])


# ---------- §3 标题人话化 ----------

def test_definition_style_title_flagged(env):
    """❌ 定义式标题（什么是X/X的定义）——开头非概念的人话化执行。"""
    o = _article()
    o["小节"][0]["标题"] = "什么是热量缺口"
    assert any("定义" in e or "概念" in e for e in _run(env, o)["errors"])


def test_term_ending_title_warns(env):
    """⚠️ 术语词收尾（档位/杠杆/映射…）——真人不会这么念。"""
    o = _article()
    o["小节"][2]["标题"] = "选定缺口档位"
    o["小节"][3]["标题"] = "配上两个保肌杠杆"
    r = _run(env, o)
    assert any("档位" in w or "人话" in w for w in r["warnings"])


def test_plain_title_ok(env):
    o = _article()
    o["小节"][2]["标题"] = "选定合适的热量缺口"
    o["小节"][3]["标题"] = "怎么同时保住肌肉"
    r = _run(env, o)
    assert not any("人话" in w for w in r["warnings"])


# ---------- §1 三决策 ----------

def test_duenneng_missing_flagged(env):
    o = _article()
    del o["读完能"]
    assert any("读完能" in e for e in _run(env, o)["errors"])


def test_duenneng_knowledge_verb_flagged(env):
    o = _article(读完能="能了解热量缺口的概念")
    assert any("读完能" in e for e in _run(env, o)["errors"])


def test_duenneng_action_ok(env):
    o = _article(读完能="能算出自己的TDEE并设定每日缺口")
    assert _run(env, o)["errors"] == []


def test_xiegei_generic_flagged(env):
    o = _article(写给="新手")
    assert any("写给" in e for e in _run(env, o)["errors"])


def test_section_count_out_of_range_warns(env):
    o = _article()
    o["小节"] = o["小节"][:3]
    r = _run(env, o)
    assert any("小节" in w or "节数" in w for w in r["warnings"])


# ---------- v1 格式守卫 ----------

def test_v1_schema_rejected(env):
    """v1 多章格式已废止，给出指路提示。"""
    v1 = {"主题": "x", "章节": [{"章": "a", "目标": "b",
                                 "卡片": ["c"], "素材": ["L3/底层逻辑.md"]}]}
    r = outline.check_outline(v1, json.loads(
        env["manifest"].read_text(encoding="utf-8")), str(env["lib"]))
    assert any("v1" in e or "模板" in e for e in r["errors"])


# ---------- find_gaps（v1 保留，行为不变） ----------

def test_find_gaps_flags_uncovered_subquestions(env):
    problems = {"problems": [{"问题": "减肥时热量缺口标准是多少"},
                             {"问题": "减脂期穿暴汗服有用吗"}]}
    r = outline.find_gaps(json.loads(env["manifest"].read_text(
        encoding="utf-8")), problems, "减脂")
    assert any("暴汗服" in g["问题"] for g in r["缺口"])


def test_find_gaps_covered_question_not_flagged(env):
    problems = {"problems": [{"问题": "减肥时热量缺口标准是多少"}]}
    r = outline.find_gaps(json.loads(env["manifest"].read_text(
        encoding="utf-8")), problems, "减脂")
    assert all("热量缺口" not in g for g in r["缺口"])


def test_find_gaps_ignores_unrelated_questions(env):
    problems = {"problems": [{"问题": "量子计算机怎么造"}]}
    r = outline.find_gaps(json.loads(env["manifest"].read_text(
        encoding="utf-8")), problems, "减脂")
    assert r["缺口"] == []
