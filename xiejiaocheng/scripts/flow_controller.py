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
from pathlib import Path

STAGES = ["init", "stage0", "stage1", "topic", "stage3", "stage4",
          "stage5", "stage6", "delivered"]

_LIB_MANIFEST = ("library", "coverage-manifest.json")
_PROBLEM_LIST = ("problem_list.json",)
_ANSWERS_MANIFEST = ("answers", "answers-manifest.json")
_OUTLINE = ("outline.json",)
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
    outline_ok = _has(tdir, *_OUTLINE)
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
        "stage4": {"satisfied": outline_ok, "asset": "outline.json",
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
        if not _has(tdir, *_OUTLINE):
            reasons.append("缺 outline.json（先跑 Stage 4 出大纲）")
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
    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(stage_status(args.dir), ensure_ascii=False, indent=1))
    elif args.cmd == "next":
        ok, reasons = validate_next(args.dir, args.to)
        print(json.dumps({"can_proceed": ok, "reasons": reasons},
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
