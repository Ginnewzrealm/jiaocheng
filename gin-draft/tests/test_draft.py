#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-draft 回归测试——每条规则对应红阶段一条真实失败样本。

基线：/tmp/gin-draft-baseline/ch1.md（"平台期"第一章，裸写无规则）
运行：python3 -m pytest tests/ -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import draft  # noqa: E402


# ---------- 夹具：基线章节（真实失败样本的来源） ----------

CH1 = "/tmp/gin-draft-baseline/ch1.md"


@pytest.fixture(scope="module")
def ch1_text():
    return open(CH1, encoding="utf-8").read()


@pytest.fixture(scope="module")
def good_text():
    """过机检的实战章（gin-draft e2e 产出）。"""
    p = "/tmp/gin-draft-e2e/ch1.md"
    if not os.path.exists(p):
        pytest.skip("e2e 实战章不存在")
    return open(p, encoding="utf-8").read()


# ---------- F4：素材锚定检查（失败样本：论断零出处） ----------

def test_anchor_rate_below_60_flagged(ch1_text):
    """基线通篇无锚点 → 锚定率远低于 60% 红线。章素材映射来自施工单，
    检查正文是否体现对素材的依赖（来源标注/引用/数据出处）。"""
    r = draft.check_chapter(ch1_text, materials=2)
    assert r["锚定率"] < 0.6


def test_anchored_text_passes():
    good = ("根据《科学网》的研究（L3/科学网），低热量饮食 3 周后基础代谢"
            "平均下降 200 千卡/日。\n\n"
            "《StatPearls》的界定（L7/StatPearls）：停滞 4 周以上才算平台期。\n\n"
            "研究（2024）进一步显示，肌肉流失占减重的 25%。")
    r = draft.check_chapter(good, materials=2)
    assert r["锚定率"] >= 0.6


# ---------- F1：章首学习契约（失败样本：开篇直接讲故事，无写给谁/能做到什么） ----------

def test_missing_opening_contract_flagged(ch1_text):
    r = draft.check_chapter(ch1_text)
    assert any("契约" in e for e in r["errors"])


def test_opening_contract_ok():
    good = ("写给正在减脂、体重突然不动的你。读完这章，你能判断自己"
            "遇到的是不是真平台期。\n\n" + "正文" * 50)
    r = draft.check_chapter(good)
    assert not any("契约" in e for e in r["errors"])


# ---------- F2：章末交付物（失败样本：只有"本章要点"，无清单/模板/表） ----------

def test_summary_only_no_deliverable_flagged(ch1_text):
    r = draft.check_chapter(ch1_text)
    assert any("交付物" in e for e in r["errors"])


def test_checkbox_deliverable_ok():
    good = "正文" * 50 + "\n\n## 自查清单\n- [ ] 条件一\n- [ ] 条件二"
    r = draft.check_chapter(good)
    assert not any("交付物" in e for e in r["errors"])


def test_table_or_template_also_counts():
    good = "正文" * 50 + "\n\n| 情况 | 判断 |\n|---|---|\n| 围度缩 | 假平台 |"
    r = draft.check_chapter(good)
    assert not any("交付物" in e for e in r["errors"])


# ---------- F3：贯穿案例在场（失败样本：大纲定了"小张"，正文零出场） ----------

def test_case_character_absent_flagged(ch1_text):
    r = draft.check_chapter(ch1_text, case_name="小张")
    assert any("案例" in e for e in r["errors"])


def test_case_character_present_ok(ch1_text):
    """同一章正文只要案例人物出现 ≥1 次即过（"用得好不好"归 Stage 6）。"""
    r = draft.check_chapter(ch1_text + "\n小张也卡在这一步。", case_name="小张")
    assert not any("案例" in e for e in r["errors"])


# ---------- F5：句式密度（失败样本："不是A，是B"一章用5次变口头禅） ----------

def test_rhetoric_density_flagged(ch1_text):
    r = draft.check_chapter(ch1_text)
    assert any("不是" in w and "密度" in w for w in r["warnings"])


def test_rhetoric_within_limit_ok():
    good = "正文" * 50 + "\n这不是失败，是保护。"
    r = draft.check_chapter(good)
    assert not any("密度" in w for w in r["warnings"])


# ---------- 禁区词表（卡兹克词表，三派一致） ----------

def test_banned_words_flagged():
    bad = "正文" * 50 + "\n说白了，这就是赋能抓手。综上所述，本质上不可否认。"
    r = draft.check_chapter(bad)
    hits = [w for w in ("说白了", "赋能", "综上所述", "本质上") if w in r["禁区词命中"]]
    assert len(hits) >= 3


def test_clean_text_no_banned_words(ch1_text):
    r = draft.check_chapter(ch1_text)
    assert r["禁区词命中"] == []


# ---------- 素材存在性（施工单引用的素材文件必须真实存在） ----------

def test_ghost_material_flagged(tmp_path):
    r = draft.check_chapter("正文", materials=["L3/幽灵.md"],
                            library=str(tmp_path))
    assert any("不存在" in e for e in r["errors"])


def test_real_material_ok(tmp_path):
    (tmp_path / "L3").mkdir()
    (tmp_path / "L3" / "a.md").write_text("x", encoding="utf-8")
    r = draft.check_chapter("正文", materials=["L3/a.md"], library=str(tmp_path))
    assert not any("不存在" in e for e in r["errors"])


# ---------- 对标 hv-analysis 写作方法论（用户拍板 2026-09-06） ----------

def test_no_loopback_flagged(ch1_text):
    """回环呼应：章首埋的钩子，章末要有 callback。
    基线章首提'平台期'，章末只有'下一章预告'，零回扣 → 拦。"""
    r = draft.check_chapter(ch1_text)
    assert any("回环" in e for e in r["errors"])


def test_loopback_ok(good_text):
    """章末段回扣章首关键词（案例名/章题词）即过。"""
    r = draft.check_chapter(good_text)
    assert not any("回环" in e for e in r["errors"])


def test_vague_summary_flagged():
    """hv-analysis'用人话写'：具体细节代替概括。
    '实现了快速增长/得到了广泛应用'类空洞概括 → 拦。"""
    bad = ("正文" * 50 + "\n\n这种方法在实践中得到了广泛应用，"
           "很多使用者都取得了明显的进步。")
    r = draft.check_chapter(bad)
    assert any("空洞" in e for e in r["errors"])


def test_specific_detail_ok(good_text):
    r = draft.check_chapter(good_text)
    assert not any("空洞" in e for e in r["errors"])


# ---------- CLI ----------

def test_cli_check_outputs_json(tmp_path):
    import json
    import subprocess
    p = tmp_path / "ch.md"
    p.write_text("正文" * 50, encoding="utf-8")
    out = subprocess.run(
        [sys.executable,
         os.path.join(os.path.dirname(__file__), "..", "scripts", "draft.py"),
         "check", "--file", str(p), "--case", "小张"],
        capture_output=True, text=True)
    r = json.loads(out.stdout)
    assert "errors" in r and "warnings" in r


# ---------- 重构阶段：堵合理化借口 ----------

def test_anchor_name_dumping_capped(tmp_path):
    """借口：章末贴一行'素材：L3/a.md、L3/b.md'凑锚定数。
    堵法：清单式贴名行（头部带素材/出处标签，或一行并列 ≥2 个 L 路径）
    最多算 1 锚点——锚定必须分布在正文里，不能一行贴完。"""
    text = "正文" * 200 + "\n\n素材清单：L3/a.md、L3/b.md、出处：《x》（2024）"
    r = draft.check_chapter(text, materials=2)
    assert r["锚定率"] < 0.6, "一行贴多个素材名只算 1 锚点，凑数无效"


def test_anchor_real_distribution_ok():
    """真锚定：三处引用分布在不同段落（2 份素材 × 每份 2 锚点 = 满分线）。"""
    text = ("根据《科学网》的研究（L3/科学网），基础代谢会下降。\n\n"
            "正文正文正文。\n\n"
            "《StatPearls》进一步指出（L7/StatPearls），停滞 4 周才算。\n\n"
            "研究（2016）显示代谢抑制可持续 6 年。")
    r = draft.check_chapter(text, materials=2)
    assert r["锚定率"] >= 0.6
