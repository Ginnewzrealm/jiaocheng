#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-answer 回归测试——每条规则对应红阶段一条真实失败样本。

运行：python3 -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import answer  # noqa: E402


# ---------- 规则1：类型判定必须有依据（失败样本：偷看 type_expected 才算"判对"） ----------

@pytest.mark.parametrize("q,expected", [
    ("减脂和减肥有什么区别？", "事实型"),       # 求定义/区别
    ("基础代谢率是什么？", "事实型"),
    ("BMI 怎么计算？", "方法型"),               # 求公式/算法（单公式也按流程写，不走事实档）
    ("减脂期的热量缺口应该怎么计算？", "方法型"),  # 求流程/公式
    ("新手一周训练怎么安排？", "方法型"),
    ("力量训练和有氧训练哪个减肥效果更好？", "争议型"),  # 存在对立阵营
    ("减脂要不要吃早餐？", "争议型"),
])
def test_classify_question(q, expected):
    r = answer.classify_question(q)
    assert r["类型"] == expected
    assert r["判定依据"], "判定依据必须显式输出，不许空"  # 红样本#1


def test_classify_fallback_unknown():
    r = answer.classify_question("今天天气怎么样？")
    assert r["类型"] == "事实型"  # 兜底归事实型（最保守档位），但仍须给依据


# ---------- 规则3：本地出处必须可机检（失败样本：url 空串无法验证） ----------

def _good_card(tmp_path):
    lib = tmp_path / "lib"
    (lib / "L3").mkdir(parents=True)
    f = lib / "L3" / "macros.md"
    f.write_text("> 来源：x\n> URL：https://example.com/a\n\n---\n\n内容", encoding="utf-8")
    return {
        "问题": "测试", "类型": "事实型", "一句话答案": "答案",
        "出处": [{"来源": "L3/macros.md", "url": "", "要点": "x"}],
        "置信度": "高", "状态": "达标",
    }, str(lib)


def test_check_card_local_path_must_exist(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"][0]["来源"] = "L3/不存在的文件.md"
    errs = answer.check_card(card, lib)
    assert any("不存在" in e for e in errs), "引用的本地文件不存在必须报错"


def test_check_card_local_ok_when_exists(tmp_path):
    card, lib = _good_card(tmp_path)
    errs = answer.check_card(card, lib)
    assert not any("不存在" in e for e in errs)


def test_l7_research_dir_counts_as_local(tmp_path):
    """e2e 实测发现：SKILL.md 约定研究补充层为 L7_研究补充/，但
    is_local_source 的 ^L[1-7]/ 正则匹配不到带后缀的层目录。"""
    lib = tmp_path / "lib"
    d = lib / "L7_研究补充"
    d.mkdir(parents=True)
    (d / "statpearls.md").write_text("x", encoding="utf-8")
    card = {"问题": "t", "类型": "事实型", "一句话答案": "a",
            "出处": [{"来源": "L7_研究补充/statpearls.md", "url": "", "要点": "x"}],
            "置信度": "中", "状态": "达标"}
    assert answer.check_card(card, str(lib)) == []


def test_check_card_web_source_needs_url(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"].append({"来源": "某网站", "url": "", "要点": "y"})
    errs = answer.check_card(card, lib)
    assert any("URL" in e for e in errs), "联网来源 url 为空必须报错（红样本#3）"


# ---------- 规则5：独立性检查（失败样本：二手转引混入；A引用B不算独立） ----------

def test_check_card_duplicate_domain_not_independent(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"] += [
        {"来源": "站A", "url": "https://a.com/x", "要点": "p"},
        {"来源": "站B转引", "url": "https://a.com/y", "要点": "p"},  # 同域转载
    ]
    warns = answer.check_independence(card["出处"])
    assert any("独立" in w for w in warns)


def test_check_card_wiki_mirrors_not_independent(tmp_path):
    srcs = [
        {"来源": "知乎", "url": "https://zhuanlan.zhihu.com/p/123", "要点": "p"},
        {"来源": "搜狐转载", "url": "https://sohu.com/a/456", "要点": "p"},
    ]
    warns = answer.check_independence(srcs)
    assert any("独立" in w for w in warns)


# ---------- 绿阶段验证发现：学术宿主误判（2026-09-06 e2e 实测） ----------

def test_same_domain_academic_papers_are_independent(tmp_path):
    """e2e 实测误报：Fothergill 2016 与 Leibel 1995 是两篇独立研究，
    只因都挂在 pubmed 域名下被警告。学术宿主按文章 ID 判独立，不按域名。"""
    srcs = [
        {"来源": "研究A", "url": "https://pubmed.ncbi.nlm.nih.gov/27136388/", "要点": "p"},
        {"来源": "研究B", "url": "https://pubmed.ncbi.nlm.nih.gov/7632212/", "要点": "q"},
    ]
    assert answer.check_independence(srcs) == []


def test_same_article_id_on_academic_host_still_not_independent(tmp_path):
    """同一篇文章的两个链接（如 pubmed 与 europepmc 镜像）仍算同一来源。"""
    srcs = [
        {"来源": "PubMed版", "url": "https://pubmed.ncbi.nlm.nih.gov/27136388/", "要点": "p"},
        {"来源": "EuropePMC镜像", "url": "https://europepmc.org/article/MED/27136388", "要点": "p"},
    ]
    warns = answer.check_independence(srcs)
    assert any("独立" in w for w in warns)


# ---------- 规则4：置信度三级判定（失败样本：三张卡全瞎打"高"） ----------

def test_confidence_high_needs_two_independent_authoritative(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"].append({"来源": "L1/官方指南.md", "url": "", "要点": "y",
                         "定级": "high"})
    # 本地 L3 一条 + L1 一条 = 两条独立权威
    os.makedirs(os.path.join(lib, "L1"), exist_ok=True)
    open(os.path.join(lib, "L1", "官方指南.md"), "w", encoding="utf-8").write("内容")
    card["争议点"] = []
    assert answer.confidence_grade(card, lib) == "高"


def test_confidence_medium_when_single_or_conflict(tmp_path):
    card, lib = _good_card(tmp_path)  # 只有一条本地出处
    assert answer.confidence_grade(card, lib) == "中"
    card["出处"].append({"来源": "站A", "url": "https://a.com/1", "要点": "p",
                         "定级": "medium"})
    card["出处"].append({"来源": "站B", "url": "https://b.com/2", "要点": "q",
                         "定级": "medium"})
    card["争议点"] = ["某点冲突"]
    assert answer.confidence_grade(card, lib) == "中"


def test_confidence_low_when_weak(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"] = [{"来源": "论坛帖", "url": "https://tieba.baidu.com/x",
                     "要点": "p", "定级": "unknown"}]
    assert answer.confidence_grade(card, lib) == "低"


# ---------- 规则8：manifest 观察哨显式分级（失败样本：机制形同虚设） ----------

def test_manifest_watchlist_flags_low_confidence(tmp_path):
    card, lib = _good_card(tmp_path)
    card["置信度"] = "低"
    card["状态"] = "达标"
    cards = [card]
    # 也覆盖"待补采"触发
    card2 = dict(card)
    card2["问题"] = "另一个问题"
    card2["状态"] = "待补采"
    cards.append(card2)
    m = answer.build_manifest(cards, "减脂", lib)
    wl = m["观察哨"]
    assert any(c["问题"] == card["问题"] and c["触发原因"] == "置信度低" for c in wl)
    assert any(c["问题"] == "另一个问题" and c["触发原因"] == "待补采" for c in wl)


def test_manifest_watchlist_empty_when_all_good(tmp_path):
    card, lib = _good_card(tmp_path)
    m = answer.build_manifest([card], "减脂", lib)
    assert m["观察哨"] == []


# ---------- CLI：validate 子命令 ----------

def test_cli_validate_reports_errors(tmp_path):
    card, lib = _good_card(tmp_path)
    card["出处"][0]["来源"] = "L3/幽灵.md"
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    r = answer.validate_card(str(p), lib)
    assert r["errors"], "机检必须检出错误"
    assert any("不存在" in e for e in r["errors"])


# ---------- 重构阶段：堵合理化借口 ----------

def test_validate_recomputes_confidence_against_claim(tmp_path):
    """借口：'凭感觉打中/打高，谁也看不出来'。
    堵法：validate 自动复算置信度，与自报不符即警告。"""
    card, lib = _good_card(tmp_path)  # 单一本地出处 → 规则复算应为"中"
    card["置信度"] = "高"              # 自报虚高
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    r = answer.validate_card(str(p), lib)
    assert r["置信度复算"] == "中"
    assert any("复算" in w for w in r["warnings"])


def test_validate_clean_card_no_false_warning(tmp_path):
    """借口反面：复算与自报一致时不许误报。"""
    card, lib = _good_card(tmp_path)
    card["置信度"] = "中"
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    r = answer.validate_card(str(p), lib)
    assert not any("复算" in w for w in r["warnings"])


def test_classify_evidence_always_present_cli(tmp_path):
    """借口：'这题一眼事实型，不用跑 classify'。堵法：卡片类型字段与
    classify 输出绑定校验——类型值必须属于三类之一且卡片须留判定依据。"""
    card, lib = _good_card(tmp_path)
    card["类型"] = "随便型"
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    r = answer.validate_card(str(p), lib)
    assert any("类型" in e for e in r["errors"])
