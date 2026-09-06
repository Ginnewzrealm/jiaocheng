#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xiejiaocheng 回归测试——每条规则对应减脂 e2e 的真实场景。

基线素材（真实场景复刻）：
- 减脂 e2e：Stage 0 资料库现成（该跳过）、Stage 1 problem_list 刚跑出（该认账）、
  答案卡还没做（不许进大纲）

运行：python3 -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import flow_controller as fc  # noqa: E402


# ---------- 夹具：搭建 tutorial 目录的各种真实状态 ----------

@pytest.fixture
def bare(tmp_path):
    """只有主题，什么都没有。"""
    return tmp_path


@pytest.fixture
def with_library(tmp_path):
    """Stage 0 完成态：资料库 + coverage-manifest（减脂 e2e 的真实起点）。"""
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "coverage-manifest.json").write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def with_problems(with_library):
    """Stage 1 也完成：problem_list.json 认账（本轮减脂刚跑完）。"""
    (with_library / "problem_list.json").write_text(
        json.dumps({"topic": "减脂", "problems": []}, ensure_ascii=False),
        encoding="utf-8")
    return with_library


def _confirm(tdir, **gates):
    (tdir / "confirmations.json").write_text(
        json.dumps(gates, ensure_ascii=False), encoding="utf-8")


def _manifest(tdir, n=2):
    ans = tdir / "answers"
    ans.mkdir(exist_ok=True)
    cards = [{"问题": f"Q{i}", "置信度": "高", "达标": True} for i in range(n)]
    (ans / "answers-manifest.json").write_text(
        json.dumps({"观察哨": [], "达标卡": cards}, ensure_ascii=False),
        encoding="utf-8")


# ---------- 资产认账：检测到产物就跳过，不重复跑 ----------

def test_stage0_satisfied_with_library(with_library):
    """减脂 e2e 场景：资料库现成 → stage0 必须标 satisfied（跳过，不重跑）。"""
    st = fc.stage_status(with_library)
    assert st["stage0"]["satisfied"] is True


def test_stage0_not_satisfied_without_manifest(bare):
    """只建了目录没有 coverage-manifest → 不算数（防"空目录冒充资料库"）。"""
    (bare / "library").mkdir()
    st = fc.stage_status(bare)
    assert st["stage0"]["satisfied"] is False


def test_stage1_satisfied_with_problem_list(with_problems):
    st = fc.stage_status(with_problems)
    assert st["stage1"]["satisfied"] is True


def test_stage1_pending_when_list_missing(with_library):
    st = fc.stage_status(with_library)
    assert st["stage1"]["satisfied"] is False


# ---------- 硬闸门：没确认不许推进 ----------

def test_gate_topic_blocks_stage3(with_problems):
    """选题没拍板 → 即使有资料库+问题清单也不许进 Stage 3。"""
    ok, reasons = fc.validate_next(with_problems, "stage3")
    assert not ok
    assert any("选题" in r for r in reasons)


def test_gate_topic_confirmed_allows_stage3(with_problems):
    _confirm(with_problems, topic="减重和减脂的区别")
    ok, _ = fc.validate_next(with_problems, "stage3")
    assert ok


def test_stage4_requires_answers_manifest(with_problems):
    """没答案卡 → 不许进大纲（大纲的原料是答案卡）。"""
    _confirm(with_problems, topic="x")
    ok, reasons = fc.validate_next(with_problems, "stage4")
    assert not ok
    assert any("answers-manifest" in r or "答案" in r for r in reasons)


def test_stage4_ok_with_manifest(with_problems):
    _confirm(with_problems, topic="x")
    _manifest(with_problems)
    ok, _ = fc.validate_next(with_problems, "stage4")
    assert ok


def test_gate_outline_blocks_stage5(with_problems):
    """大纲机检过了但你没确认 → 不许开写（防 AI 自嗨写正文）。"""
    _confirm(with_problems, topic="x")
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "stage5")
    assert not ok
    assert any("大纲" in r for r in reasons)


def test_stage5_ok_after_outline_confirmed(with_problems):
    _confirm(with_problems, topic="x", outline=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ok, _ = fc.validate_next(with_problems, "stage5")
    assert ok


def test_stage6_requires_chapters(with_problems):
    """一章都没写 → 质检无米下锅。"""
    _confirm(with_problems, topic="x", outline=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "stage6")
    assert not ok


def test_gate_l4_and_publish_block_delivery(with_problems):
    """机检报告有了但 L4 人审/发布确认缺一个 → 不许交付。"""
    _confirm(with_problems, topic="x", outline=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ch = with_problems / "chapters"
    ch.mkdir()
    (ch / "ch1.md").write_text("# 第一章", encoding="utf-8")
    qc = with_problems / "qc"
    qc.mkdir()
    (qc / "report.json").write_text(json.dumps({"verdict": "通过"}),
                                    encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "delivered")
    assert not ok
    assert any("L4" in r for r in reasons)
    assert any("发布" in r for r in reasons)


def test_delivery_ok_with_all_confirmations(with_problems):
    _confirm(with_problems, topic="x", outline=True,
             l4=["温度感", "独特性", "姿态", "心流"], publish=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ch = with_problems / "chapters"
    ch.mkdir()
    (ch / "ch1.md").write_text("# 第一章", encoding="utf-8")
    ck = with_problems / "checks"
    ck.mkdir()
    (ck / "ch1.draft.json").write_text(json.dumps({"errors": 0}),
                                       encoding="utf-8")
    qc = with_problems / "qc"
    qc.mkdir()
    (qc / "report.json").write_text(json.dumps({"verdict": "通过"}),
                                    encoding="utf-8")
    ok, _ = fc.validate_next(with_problems, "delivered")
    assert ok


# ---------- 机检证据：errors 不归零不算过 ----------

def test_stage5_requires_clean_draft_check(with_problems):
    """借口：章文件存在就算写完。堵法：每章要配 errors=0 的机检报告。"""
    _confirm(with_problems, topic="x", outline=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ch = with_problems / "chapters"
    ch.mkdir()
    (ch / "ch1.md").write_text("# 第一章", encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "stage6")
    assert not ok
    assert any("机检" in r or "draft" in r for r in reasons)


# ---------- 重构期堵口：坏产物、空章、假报告、未知阶段 ----------

def test_corrupt_manifest_not_recognized(bare):
    """借口：touch 一个坏 manifest 冒充资料库。堵法：必须能解析出 JSON。"""
    lib = bare / "library"
    lib.mkdir()
    (lib / "coverage-manifest.json").write_text("not json{", encoding="utf-8")
    st = fc.stage_status(bare)
    assert st["stage0"]["satisfied"] is False


def test_empty_chapter_not_counted(with_problems):
    """借口：touch 空 .md 冒充写完的章。堵法：空章不算章节。"""
    _confirm(with_problems, topic="x", outline=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ch = with_problems / "chapters"
    ch.mkdir()
    (ch / "ch1.md").write_text("   \n", encoding="utf-8")
    ck = with_problems / "checks"
    ck.mkdir()
    (ck / "ch1.draft.json").write_text(json.dumps({"errors": 0}),
                                       encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "stage6")
    assert not ok
    assert any("章" in r for r in reasons)


def test_qc_verdict_fail_blocks_delivery(with_problems):
    """借口：随便写个 report.json 就算质检过。堵法：verdict=不通过 不许交付。"""
    _confirm(with_problems, topic="x", outline=True,
             l4=["温度感"], publish=True)
    _manifest(with_problems)
    (with_problems / "outline.json").write_text("{}", encoding="utf-8")
    ch = with_problems / "chapters"
    ch.mkdir()
    (ch / "ch1.md").write_text("# 第一章\n\n正文。" * 20, encoding="utf-8")
    ck = with_problems / "checks"
    ck.mkdir()
    (ck / "ch1.draft.json").write_text(json.dumps({"errors": 0}),
                                       encoding="utf-8")
    qc = with_problems / "qc"
    qc.mkdir()
    (qc / "report.json").write_text(
        json.dumps({"verdict": "不通过"}, ensure_ascii=False),
        encoding="utf-8")
    ok, reasons = fc.validate_next(with_problems, "delivered")
    assert not ok
    assert any("不通过" in r for r in reasons)


def test_unknown_stage_rejected(with_problems):
    ok, reasons = fc.validate_next(with_problems, "stage9")
    assert not ok
    assert any("未知" in r for r in reasons)


# ---------- CLI ----------

def test_cli_status_outputs_json(tmp_path):
    out = os.popen(
        f"{sys.executable} {os.path.join(os.path.dirname(__file__), '..', 'scripts', 'flow_controller.py')} "
        f"status --dir {tmp_path}").read()
    r = json.loads(out)
    assert "stage0" in r and "stage6" in r


def test_cli_next_blocks_without_assets(tmp_path):
    out = os.popen(
        f"{sys.executable} {os.path.join(os.path.dirname(__file__), '..', 'scripts', 'flow_controller.py')} "
        f"next --dir {tmp_path} --to stage4").read()
    r = json.loads(out)
    assert r["can_proceed"] is False
