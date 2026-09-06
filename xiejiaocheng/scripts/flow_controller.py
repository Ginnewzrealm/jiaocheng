#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xiejiaocheng 编排器：阶段状态机 + 硬闸门校验 + 产物认账检测。

设计决策（2026-09-06 用户拍板）：
- 七原子技能独立可触发，本编排器只调不改
- 资产认账：检测到上游标准产物（problem_list.json / answers-manifest.json /
  大纲.json / 章文件）即标 satisfied，不重复跑——单独跑的成果能回流流水线
- 硬闸门 4 个：选题拍板 / 大纲确认 / L4 终审 / 发布
- 子任务循环：批内自动，批边界需确认（见 SKILL.md 进度条规则）

约定目录布局（tutorial 工作目录，可用软链指到真实位置）：
  <dir>/library/coverage-manifest.json   Stage 0 产物
  <dir>/problem_list.json                Stage 1 产物
  <dir>/answers/answers-manifest.json    Stage 3 产物
  <dir>/outline.json                     Stage 4 产物
  <dir>/chapters/*.md                    Stage 5 章文件
  <dir>/checks/<章名>.draft.json         Stage 5 机检报告（errors 必须 = 0）
  <dir>/qc/report.json                   Stage 6 质检报告
  <dir>/confirmations.json               4 硬闸门的确认记录

用法：
  python3 scripts/flow_controller.py status --dir <tutorial_id目录>
  python3 scripts/flow_controller.py next --dir <d> --to <stage> [--yes]
"""
import argparse
import json
import sys
from pathlib import Path

STAGES = ["init", "stage0", "stage1", "topic", "stage3", "stage4",
          "stage5", "stage6", "delivered"]

# 闸门 → 所属 stage（回环时按 stage 序重置下游闸门，指南 §8.3）
GATE_STAGE = {"topic": "topic", "outline": "stage4",
              "l4": "stage6", "publish": "delivered"}

# 软回环允许的目标：只限"带闸门决策"的节点。
# 纯产物阶段（0/1/3/5）由资产认账接管——要重做请直接重跑原子技能。
ROLLBACK_ALLOWED = {"topic", "stage4", "stage6", "delivered"}

# resume 时按序探测首个拦截点（闸门/资产），用于阻塞提示
GATE_CHECK_ORDER = ["stage3", "stage4", "stage5", "stage6", "delivered"]

_LIB_MANIFEST = ("library", "coverage-manifest.json")
_PROBLEM_LIST = ("problem_list.json",)
_ANSWERS_MANIFEST = ("answers", "answers-manifest.json")
_OUTLINES_DIR = "outlines"
_QC_REPORT = ("qc", "report.json")
_CONFIRMATIONS = "confirmations.json"


def _has(tdir, *parts):
    return (tdir.joinpath(*parts)).is_file()


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _load_confirmations(tdir):
    data = _load_json(tdir / _CONFIRMATIONS)
    return data if isinstance(data, dict) else {}


def _chapters(tdir):
    """章节文件：非空 .md 才算（空章/touch 冒充不算写完）。"""
    ch = tdir / "chapters"
    if not ch.is_dir():
        return []
    out = []
    for p in sorted(ch.glob("*.md")):
        try:
            if p.read_text(encoding="utf-8", errors="ignore").strip():
                out.append(p)
        except OSError:
            continue
    return out


def _outlines(tdir):
    """v2 Stage 4 产物：outlines/ 下非空 .json（一题一文，一篇一文件）。"""
    od = tdir / _OUTLINES_DIR
    if not od.is_dir():
        return []
    out = []
    for p in sorted(od.glob("*.json")):
        try:
            if p.read_text(encoding="utf-8", errors="ignore").strip():
                out.append(p)
        except OSError:
            continue
    return out


def _draft_clean(tdir, chapter_md):
    """Stage 5 机检报告：errors 必须归 0，否则章文件存在也不算写完。"""
    data = _load_json(tdir / "checks" / (chapter_md.stem + ".draft.json"))
    return isinstance(data, dict) and data.get("errors") == 0


def _lib_ok(tdir):
    """资料库认账：coverage-manifest.json 必须存在且能解析（防 touch 冒充）。"""
    data = _load_json(tdir.joinpath(*_LIB_MANIFEST))
    return data is not None


def _qc_verdict(tdir):
    data = _load_json(tdir.joinpath(*_QC_REPORT))
    if isinstance(data, dict):
        return data.get("verdict")
    return None


def stage_status(tdir):
    """扫描 tutorial 目录，返回各阶段产物/闸门状态（资产认账）。"""
    tdir = Path(tdir)
    conf = _load_confirmations(tdir)
    lib_ok = _lib_ok(tdir)
    pl_ok = _has(tdir, *_PROBLEM_LIST)
    manifest_ok = _has(tdir, *_ANSWERS_MANIFEST)
    outline_ok = bool(_outlines(tdir))
    chs = _chapters(tdir)
    checks = {c.name: _draft_clean(tdir, c) for c in chs}
    qc_verdict = _qc_verdict(tdir)
    return {
        "stage0": {"satisfied": lib_ok,
                   "asset": "library/coverage-manifest.json"},
        "stage1": {"satisfied": pl_ok, "asset": "problem_list.json"},
        "topic": {"satisfied": bool(conf.get("topic")),
                  "gate": "选题拍板",
                  "confirmed": conf.get("topic")},
        "stage3": {"satisfied": manifest_ok,
                   "asset": "answers/answers-manifest.json"},
        "stage4": {"satisfied": outline_ok, "asset": "outlines/*.json",
                   "outlines": len(_outlines(tdir)),
                   "gate": "大纲确认", "gate_passed": bool(conf.get("outline"))},
        "stage5": {"satisfied": bool(chs) and all(checks.values()),
                   "chapters": len(chs),
                   "checks_clean": sum(checks.values())},
        "stage6": {"satisfied": qc_verdict is not None,
                   "asset": "qc/report.json",
                   "verdict": qc_verdict},
        "delivered": {"satisfied": bool(conf.get("l4")) and bool(conf.get("publish")),
                      "gates": ["L4人审", "发布"]},
        "confirmations": conf,
    }


def validate_next(tdir, target):
    """校验能否推进到 target stage。返回 (can_proceed, reasons[])。

    两类拦截：
    1. 资产缺失——上游产物不存在（不许空转下一阶段）
    2. 硬闸门未确认——confirmations.json 里缺对应记录（不许 AI 自嗨推进）
    """
    tdir = Path(tdir)
    if target not in STAGES:
        return False, [f"未知阶段：{target}（可选：{'/'.join(STAGES)}）"]
    conf = _load_confirmations(tdir)
    idx = STAGES.index(target)
    reasons = []

    if idx >= STAGES.index("stage3"):
        if not conf.get("topic"):
            reasons.append("硬闸门未过：选题未拍板"
                           f"（{_CONFIRMATIONS} 缺 topic）")
    if idx >= STAGES.index("stage4"):
        if not _has(tdir, *_ANSWERS_MANIFEST):
            reasons.append("缺 answers/answers-manifest.json"
                           "（先跑 Stage 3 找答案）")
    if idx >= STAGES.index("stage5"):
        if not _outlines(tdir):
            reasons.append("缺 outlines/*.json（先跑 Stage 4 出大纲，一题一文）")
        if not conf.get("outline"):
            reasons.append("硬闸门未过：大纲未确认"
                           f"（{_CONFIRMATIONS} 缺 outline=true）")
    if idx >= STAGES.index("stage6"):
        chs = _chapters(tdir)
        if not chs:
            reasons.append("chapters/ 下没有章节文件（先跑 Stage 5 写作）")
        else:
            bad = [c.name for c in chs if not _draft_clean(tdir, c)]
            if bad:
                reasons.append(
                    "Stage 5 机检未清零（errors≠0 或缺报告）："
                    + ", ".join(bad))
    if idx >= STAGES.index("delivered"):
        verdict = _qc_verdict(tdir)
        if verdict is None:
            reasons.append("缺 qc/report.json（先跑 Stage 6 质检）")
        elif verdict not in ("通过", "minor"):
            reasons.append(f"Stage 6 质检结论为「{verdict}」，修完复审才能交付")
        if not conf.get("l4"):
            reasons.append("硬闸门未过：L4 人审未签"
                           f"（{_CONFIRMATIONS} 缺 l4）")
        if not conf.get("publish"):
            reasons.append("硬闸门未过：发布未确认"
                           f"（{_CONFIRMATIONS} 缺 publish=true）")
    return (not reasons), reasons


def _write_confirmations(tdir, conf):
    (tdir / _CONFIRMATIONS).write_text(
        json.dumps(conf, ensure_ascii=False, indent=1), encoding="utf-8")


def _append_progress(tdir, line):
    with open(tdir / "progress.md", "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def cmd_resume(tdir):
    """会话恢复（指南 §7.2）：完整宏观仪表盘 + 当前阻塞（若有）。"""
    from progress_reporter import blocker_hint, current_stage, render_macro

    tdir = Path(tdir)
    st = stage_status(tdir)
    blocker = ""
    # 只有推进到选题及以后才可能有闸门/资产拦截；此前是"活没干完"而非阻塞
    if STAGES.index(current_stage(st)) >= STAGES.index("topic"):
        for target in GATE_CHECK_ORDER:
            ok, reasons = validate_next(tdir, target)
            if not ok:
                blocker = blocker_hint(reasons)
                break
    return {"current_stage": current_stage(st),
            "dashboard": render_macro(st), "blocker": blocker}


def cmd_rollback(tdir, target):
    """软回环（指南 §8.3）：重置目标及下游闸门 + 锚定当前阶段；产物不动。"""
    from progress_reporter import render_macro

    tdir = Path(tdir)
    if target not in STAGES:
        return 2, {"error": f"未知回退目标：{target}（可选：{'/'.join(STAGES)}）"}
    if target not in ROLLBACK_ALLOWED:
        return 2, {"error": f"{target} 是产物认账阶段，已完成/认账后不支持回退；"
                            "要重做请直接重跑对应原子技能，或先移走其产物"}
    st = stage_status(tdir)
    if not st[target]["satisfied"]:
        return 2, {"error": f"{target} 尚无完成产物，无需回退"}
    conf = st["confirmations"]
    reset = [g for g, gs in GATE_STAGE.items()
             if STAGES.index(gs) >= STAGES.index(target)]
    for g in reset:
        conf.pop(g, None)
    conf["rolled_back_to"] = target
    _write_confirmations(tdir, conf)
    _append_progress(tdir, f"- 回环🔁：rollback → {target}（重置闸门："
                           f"{'/'.join(reset)}；产物文件保留）")
    return 0, {"rolled_back_to": target, "reset_gates": reset,
               "note": "软回环：产物文件未动",
               "dashboard": render_macro(stage_status(tdir))}


def cmd_confirm(tdir, topic=None, gate=None, l4_items=None):
    """闸门拍板落盘（主会话调用）；任何闸门确认都会清除软回环锚点。"""
    tdir = Path(tdir)
    conf = _load_confirmations(tdir)
    changed = []
    if topic is not None:
        conf["topic"] = topic
        changed.append("topic")
    if gate is not None:
        if gate not in GATE_STAGE:
            return 2, {"error": f"未知闸门：{gate}（可选：{'/'.join(GATE_STAGE)}）"}
        conf[gate] = l4_items if gate == "l4" and l4_items else True
        changed.append(gate)
    if not changed:
        return 2, {"error": "没给任何确认内容（--topic / --gate）"}
    if conf.pop("rolled_back_to", None):
        changed.append("rolled_back_to(清除)")
    _write_confirmations(tdir, conf)
    _append_progress(tdir, f"- 闸门拍板：{'/'.join(changed)}")
    return 0, {"confirmed": changed, "confirmations": conf}


def main():
    ap = argparse.ArgumentParser(description="xiejiaocheng 流程控制")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="当前各阶段产物/闸门状态")
    s.add_argument("--dir", required=True)
    n = sub.add_parser("next", help="校验能否推进到目标 stage")
    n.add_argument("--dir", required=True)
    n.add_argument("--to", required=True, choices=STAGES)
    n.add_argument("--yes", action="store_true",
                   help="占位：确认动作由主会话记录到 confirmations.json")
    r = sub.add_parser("resume", help="会话恢复：宏观仪表盘+阻塞提示")
    r.add_argument("--dir", required=True)
    b = sub.add_parser("rollback", help="软回环：重置下游闸门，产物不动")
    b.add_argument("--dir", required=True)
    b.add_argument("--to", required=True, help="回退目标（topic/stage4/stage6/delivered）")
    c = sub.add_parser("confirm", help="闸门拍板写入 confirmations.json")
    c.add_argument("--dir", required=True)
    c.add_argument("--topic", help="选题拍板内容")
    c.add_argument("--gate", choices=list(GATE_STAGE), help="闸门名")
    c.add_argument("--l4-items", help="L4 人审签字项，逗号分隔")
    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(stage_status(args.dir), ensure_ascii=False, indent=1))
    elif args.cmd == "next":
        ok, reasons = validate_next(args.dir, args.to)
        print(json.dumps({"can_proceed": ok, "reasons": reasons},
                         ensure_ascii=False, indent=1))
    elif args.cmd == "resume":
        print(json.dumps(cmd_resume(args.dir), ensure_ascii=False, indent=1))
    elif args.cmd == "rollback":
        code, payload = cmd_rollback(args.dir, args.to)
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        sys.exit(code)
    elif args.cmd == "confirm":
        l4 = [x for x in (args.l4_items or "").split(",") if x.strip()] or None
        code, payload = cmd_confirm(args.dir, topic=args.topic,
                                    gate=args.gate, l4_items=l4)
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        sys.exit(code)


if __name__ == "__main__":
    main()
