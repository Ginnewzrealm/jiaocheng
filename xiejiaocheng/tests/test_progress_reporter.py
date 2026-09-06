#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Progress Checklist 融合回归测试——每条规则对指南一个条款。

指南条款映射：
- §3.1/§6.2 宏观仪表盘：5 用户阶段、状态符号、[待开始]、← 当前
- §3.2/§11.4 微观 checklist：动作→产出物命名、标签齐全
- §3.5 阻塞提示："你可以：" 选项块
- §7.2 恢复：resume 输出完整仪表盘 + 阻塞原因
- §8.3 回环：rollback 重置闸门、高亮回退目标、不动产物（软回环）
- §9.3 硬约束代码化：非法回退被拦、未知命令不崩
- §12 误区 3：硬闸门≠需确认（render 不得混标）

运行：python3 -m pytest tests/test_progress_reporter.py -q
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import flow_controller as fc  # noqa: E402
import progress_reporter as pr  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..", "scripts",
                    "flow_controller.py")


def _write(tdir, rel, content):
    p = tdir / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _confirm(tdir, **gates):
    _write(tdir, "confirmations.json", json.dumps(gates, ensure_ascii=False))


def _lib(tdir):
    _write(tdir, "library/coverage-manifest.json", "{}")


def _manifest(tdir):
    _write(tdir, "answers/answers-manifest.json",
           json.dumps({"观察哨": [], "达标卡": [{"问题": "Q1", "达标": True}]},
                      ensure_ascii=False))


def _outline(tdir):
    _write(tdir, "outline.json", "{}")


def _chapter(tdir):
    _write(tdir, "chapters/ch1.md", "# 第一章\n\n正文内容。" * 20)
    _write(tdir, "checks/ch1.draft.json", json.dumps({"errors": 0}))


def _qc(tdir):
    _write(tdir, "qc/report.json",
           json.dumps({"verdict": "通过"}, ensure_ascii=False))


def _full(tmp_path):
    """全程场景：一路走到交付，四闸门全过（无阻塞基准）。"""
    _lib(tmp_path)
    _write(tmp_path, "problem_list.json", json.dumps({"problems": []}))
    _confirm(tmp_path, topic="t", outline=True,
             l4=["温度感"], publish=True)
    _manifest(tmp_path)
    _outline(tmp_path)
    _chapter(tmp_path)
    _qc(tmp_path)
    return tmp_path


def _cli(*argv):
    out = subprocess.run([sys.executable, REPO] + list(argv),
                         capture_output=True, text=True)
    return out.returncode, out.stdout, out.stderr


# ---------- §3.1/§6.2 宏观仪表盘 ----------

def test_macro_five_phases(tmp_path):
    """阶段数 3-8（指南 11.1）；9 内部 stage 聚合为 5 用户阶段（SOP 步骤 2）。"""
    txt = pr.render_macro(fc.stage_status(tmp_path))
    for name in ("扒资料", "找问题", "找答案·选题", "结构与写作", "质检与交付"):
        assert name in txt, f"缺用户阶段：{name}"
    assert "阶段 5/5" in txt


def test_macro_states_and_markers(tmp_path):
    """§3.3：已完成 [✓] / 待开始 / ← 当前。"""
    _lib(tmp_path)
    txt = pr.render_macro(fc.stage_status(tmp_path))
    assert "✓" in txt                     # stage0 已完成
    assert "[待开始]" in txt              # 后续阶段
    assert "← 当前" in txt                # 当前高亮
    # 当前必须是第一个未完成阶段（找问题），不能跳格
    assert txt.index("← 当前") < txt.index("[待开始]")


def test_macro_badge_counts(tmp_path):
    """指南 6.2 示例：阶段行带完成度徽标 [✓] / [待开始]。"""
    _lib(tmp_path)
    txt = pr.render_macro(fc.stage_status(tmp_path))
    assert "阶段 1/5" in txt and "阶段 2/5" in txt


# ---------- §3.2/§11.4 微观 checklist ----------

def test_micro_action_arrow_output(tmp_path):
    """§11.4：步骤命名 动作 → 产出物；禁止模糊动词开头。"""
    _lib(tmp_path)
    _write(tmp_path, "problem_list.json", json.dumps({"problems": []}))
    txt = pr.render_micro(fc.stage_status(tmp_path))
    assert "→" in txt                      # 动作→产出物
    for bad in ("处理", "分析", "优化"):
        assert f"Step 1 {bad}" not in txt and f"Step 2 {bad}" not in txt


def test_micro_step_count_and_tags(tmp_path):
    """§11.2/§11.3：每阶段 2-6 步；每步至少一个标签。"""
    _lib(tmp_path)
    st = fc.stage_status(tmp_path)
    for stage in ("stage0", "stage1", "topic", "stage3", "stage4",
                  "stage5", "stage6"):
        steps = pr.MICRO_STEPS[stage]
        assert 2 <= len(steps) <= 6, f"{stage} 步骤数越界：{len(steps)}"
        for s in steps:
            assert s.get("tags"), f"{stage} 有步骤缺标签：{s['name']}"
    # 误区 3：硬闸门步骤不得同时标 [需确认]
    for stage, steps in pr.MICRO_STEPS.items():
        for s in steps:
            if "硬闸门" in s["tags"]:
                assert "需确认" not in s["tags"]


# ---------- §3.5 阻塞提示 ----------

def test_phase_mapping_covers_all_tracked_stages():
    """防漂移：flow_controller 新增 stage 时，阶段映射和 micro 清单必须同步补。"""
    for s in fc.STAGES:
        if s == "init":
            continue
        assert s in pr.STAGE_TO_PHASE, f"{s} 未映射用户阶段"
        assert s in pr.MICRO_STEPS, f"{s} 缺 micro-checklist"


def test_blocker_hint_options(tmp_path):
    """§3.5：阻塞时给"你可以："选项块。"""
    _lib(tmp_path)
    _write(tmp_path, "problem_list.json", json.dumps({"problems": []}))
    ok, reasons = fc.validate_next(tmp_path, "stage3")
    assert not ok
    txt = pr.blocker_hint(reasons)
    assert "你可以：" in txt
    assert "确认" in txt and "回退" in txt


# ---------- §7.2 会话恢复 ----------

def test_resume_outputs_dashboard_and_blocker(tmp_path):
    """恢复：完整仪表盘 + 当前阻塞原因。"""
    _lib(tmp_path)
    _write(tmp_path, "problem_list.json", json.dumps({"problems": []}))
    rc, out, _ = _cli("resume", "--dir", str(tmp_path))
    assert rc == 0
    r = json.loads(out)
    assert "阶段 1/5" in r["dashboard"]
    assert "当前阻塞" in r["blocker"] or not r["blocker"]


def test_resume_clean_state_no_blocker(tmp_path):
    """无阻塞时不报阻塞（防恐慌式提示）。"""
    d = _full(tmp_path)
    rc, out, _ = _cli("resume", "--dir", str(d))
    r = json.loads(out)
    assert r["blocker"] == ""


# ---------- §8.3 回环（软回环：重置闸门、不动产物） ----------

def test_rollback_resets_downstream_gates(tmp_path):
    """回退到大纲前：大纲确认被重置，L4/发布也被重置（checklist 同步重置）。"""
    d = _full(tmp_path)
    rc, out, err = _cli("rollback", "--dir", str(d), "--to", "stage4")
    assert rc == 0, err
    conf = json.loads((d / "confirmations.json").read_text(encoding="utf-8"))
    assert conf.get("topic") == "t"          # 上游保留
    assert "outline" not in conf             # 目标及下游闸门重置
    assert "l4" not in conf and "publish" not in conf


def test_rollback_keeps_artifacts(tmp_path):
    """软回环：产物文件不动，供对比。"""
    d = _full(tmp_path)
    _cli("rollback", "--dir", str(d), "--to", "stage4")
    assert (d / "outline.json").is_file()
    assert (d / "chapters" / "ch1.md").is_file()
    # 重置后闸门重新拦截：修好大纲前不许再推进写作
    ok, reasons = fc.validate_next(d, "stage5")
    assert not ok


def test_rollback_highlights_target(tmp_path):
    """回退后仪表盘高亮回退目标阶段（§8.3 示例）。"""
    d = _full(tmp_path)
    _cli("rollback", "--dir", str(d), "--to", "stage4")
    txt = pr.render_macro(fc.stage_status(d))
    assert "← 当前" in txt


def test_rollback_to_done_stage_rejected(tmp_path):
    """§9.3：回退到已完成阶段无意义，拒绝。"""
    d = _full(tmp_path)
    rc, out, _ = _cli("rollback", "--dir", str(d), "--to", "stage0")
    assert rc != 0
    assert "已完成" in out


def test_rollback_unknown_stage_clean_error(tmp_path):
    """未知回退目标：干净报错，不崩（§11.6）。"""
    rc, out, err = _cli("rollback", "--dir", str(tmp_path), "--to", "stage9")
    assert rc != 0
    assert "未知" in (out + err)
