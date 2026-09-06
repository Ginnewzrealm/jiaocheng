#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-outline 回归测试——每条规则对应红阶段一条真实失败样本（F1-F7）。

运行：python3 -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import outline  # noqa: E402


# ---------- 测试夹具 ----------

@pytest.fixture
def env(tmp_path):
    """造一个最小资料库 + 答案卡 manifest + 问题清单。"""
    lib = tmp_path / "lib"
    (lib / "L3").mkdir(parents=True)
    (lib / "L3" / "a.md").write_text("x", encoding="utf-8")
    (lib / "L3" / "b.md").write_text("x", encoding="utf-8")
    manifest = {
        "topic": "减脂",
        "cards": [
            {"问题": "进入减脂平台期该怎么办？", "类型": "方法型", "置信度": "中",
             "状态": "达标"},
            {"问题": "减脂和减肥有什么区别？", "类型": "事实型", "置信度": "高",
             "状态": "达标"},
        ],
    }
    problems = [
        {"id": "P011", "text": "进入减脂平台期该怎么办？", "total_frequency": 9},
        {"id": "P023", "text": "平台期一般会持续多久？", "total_frequency": 4},
        {"id": "P001", "text": "减脂和减肥有什么区别？", "total_frequency": 3},
    ]
    return {"lib": str(lib), "manifest": manifest, "problems": problems}


def _outline(**over):
    o = {
        "主题": "减脂平台期",
        "目标读者": "新手",
        "贯穿案例": "案例小张",
        "章节": [
            {"章": "什么是平台期", "目标": "能判断真假平台期",
             "卡片": ["进入减脂平台期该怎么办？"], "素材": ["L3/a.md"]},
            {"章": "怎么破", "目标": "能执行五步排查流程",
             "卡片": ["进入减脂平台期该怎么办？"], "素材": ["L3/b.md"]},
        ],
    }
    o.update(over)
    return o


# ---------- F2：缺口判定必须有标准（失败样本：缺口清单恒空） ----------

def test_find_gaps_flags_uncovered_subquestions(env):
    """问题清单里与主题相关的"平台期一般会持续多久"没有对应答案卡
    → 必须进缺口清单。红阶段基线直接交了空清单。"""
    gaps = outline.find_gaps(env["manifest"], env["problems"], "减脂平台期")
    assert any("持续多久" in g["问题"] for g in gaps)


def test_find_gaps_covered_question_not_flagged(env):
    gaps = outline.find_gaps(env["manifest"], env["problems"], "减脂平台期")
    assert not any("进入减脂平台期" in g["问题"] for g in gaps)


def test_find_gaps_ignores_unrelated_questions(env):
    """"减脂和减肥区别"与"平台期"主题无关，不许混进缺口。"""
    gaps = outline.find_gaps(env["manifest"], env["problems"], "减脂平台期")
    assert not any("区别" in g["问题"] for g in gaps)


# ---------- F1：映射注水检查（失败样本：一张卡映射全部章节） ----------

def test_same_card_in_every_chapter_flagged(env):
    o = _outline()
    o["章节"] = [{"章": f"第{i}章", "目标": "能执行流程",
                  "卡片": ["进入减脂平台期该怎么办？"], "素材": ["L3/a.md"]}
                 for i in range(4)]
    warns = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("注水" in w for w in warns)


def test_normal_mapping_not_flagged(env):
    warns = outline.check_outline(_outline(), env["manifest"], env["lib"])
    assert not any("注水" in w for w in warns)


# ---------- F5：素材幽灵引用（原则继承自 gin-answer 出处机检） ----------

def test_ghost_material_file_flagged(env):
    o = _outline()
    o["章节"][0]["素材"] = ["L3/幽灵文件.md"]
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("不存在" in e for e in errs)


def test_ghost_card_flagged(env):
    o = _outline()
    o["章节"][0]["卡片"] = ["库里没有的问题？"]
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("不在答案卡库" in e for e in errs)


def test_valid_outline_passes_material_check(env):
    errs = outline.check_outline(_outline(), env["manifest"], env["lib"])
    assert not any("不存在" in e for e in errs)


# ---------- F3：章节目标必须是动作动词（course-outline 五决策落地） ----------

def test_chapter_objective_missing_flagged(env):
    o = _outline()
    del o["章节"][0]["目标"]
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("目标" in e for e in errs)


def test_chapter_objective_knowledge_verb_flagged(env):
    o = _outline()
    o["章节"][0]["目标"] = "学一下平台期的东西"
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("动作动词" in e for e in errs)


def test_chapter_objective_action_verb_ok(env):
    errs = outline.check_outline(_outline(), env["manifest"], env["lib"])
    assert not any("动作动词" in e for e in errs)


# ---------- F6：排序合法性——知识章必须在动作章之前 ----------

def test_action_chapter_before_knowledge_flagged(env):
    """脚踩西瓜皮：先讲'怎么破'再讲'什么是平台期'必须被拦。"""
    o = _outline()
    o["章节"] = [
        {"章": "怎么破", "目标": "能执行五步排查流程", "卡片": ["进入减脂平台期该怎么办？"], "素材": ["L3/b.md"]},
        {"章": "什么是平台期", "目标": "能说出平台期定义", "卡片": ["进入减脂平台期该怎么办？"], "素材": ["L3/a.md"]},
    ]
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("排序" in e or "先备" in e for e in errs)


def test_knowledge_before_action_ok(env):
    errs = outline.check_outline(_outline(), env["manifest"], env["lib"])
    assert not any("排序" in e or "先备" in e for e in errs)


# ---------- F7：贯穿案例钉死检查 ----------

def test_missing_running_case_flagged(env):
    o = _outline()
    del o["贯穿案例"]
    errs = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("贯穿案例" in e for e in errs)


# ---------- 每张达标卡必须被用到（Socialpranker synthesis gap 校验） ----------

def test_undrafted_card_flagged(env):
    """答案库里"减脂和减肥有什么区别"达标卡没被任何章节用到
    → 要么映射进大纲，要么进缺口说明（synthesis gap 防白找）。"""
    o = _outline()
    warns = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("未使用" in w for w in warns)


# ---------- 重构阶段：堵合理化借口 ----------

def test_skipped_card_without_reason_flagged(env):
    """借口：'不用的卡全塞进未采用列表就免检了'。
    堵法：未采用必须给理由，没理由的警告。"""
    o = _outline()
    o["未采用卡片"] = ["减脂和减肥有什么区别？"]
    r = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("未采用" in w and "理由" in w for w in r)


def test_skipped_card_with_reason_ok(env):
    o = _outline()
    o["未采用卡片"] = ["减脂和减肥有什么区别？"]
    o["未采用理由"] = {"减脂和减肥有什么区别？": "与平台期主题偏离，留给入门篇"}
    r = outline.check_outline(o, env["manifest"], env["lib"])
    assert not any("未使用" in w for w in r)


def test_all_cards_skipped_flagged(env):
    """借口：'全部弃用'等于大纲和答案库脱节，机器必须拦。"""
    o = _outline()
    o["章节"] = []
    o["未采用卡片"] = list(o["未采用理由"] or {}) if o.get("未采用理由") else []
    # 把两张达标卡全部声明弃用（各带理由）
    o["未采用卡片"] = ["进入减脂平台期该怎么办？", "减脂和减肥有什么区别？"]
    o["未采用理由"] = {"进入减脂平台期该怎么办？": "x", "减脂和减肥有什么区别？": "y"}
    r = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("全部" in e or "脱节" in e for e in r)


def test_neng_plus_knowledge_verb_flagged(env):
    """借口：'能了解平台期概念'——用'能'字开头伪装动作目标。
    堵法：能/会+知识动词的组合按知识章处理且单独警告。"""
    o = _outline()
    o["章节"][0]["目标"] = "能了解平台期的概念"
    r = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("伪装" in e or "动作动词" in e for e in r)


def test_material_dir_not_file_flagged(env):
    """借口：素材写个目录路径凑数（os.path.exists 对目录也 True）。
    堵法：必须是文件。"""
    o = _outline()
    o["章节"][0]["素材"] = ["L3"]
    r = outline.check_outline(o, env["manifest"], env["lib"])
    assert any("不是文件" in e or "不存在" in e for e in r)
