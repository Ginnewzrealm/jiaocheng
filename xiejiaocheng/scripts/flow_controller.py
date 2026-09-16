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
  <dir>/outlines/*.json                  Stage 4 v3 产物
  <dir>/chapters/*.md                    Stage 5 章文件
  <dir>/checks/<章名>.draft.json         Stage 5 机检报告（errors=[] 且哈希有效）
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
from tutorial_contract import (VERSION, cli_error, contract_errors, current_report,
    diagnostic, finish, nonempty, snapshots, stamp, write_json)

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


def _answers_ok(tdir):
    data = _load_json(tdir.joinpath(*_ANSWERS_MANIFEST))
    if not current_report(data, checker="answers-manifest"):
        return False
    cards = data.get("cards")
    return (isinstance(cards, list) and bool(cards)
            and all(isinstance(c, dict) and c.get("schema_version") == VERSION
                    and c.get("状态") == "达标" and c.get("置信度") in ("高", "中")
                    and nonempty(c.get("问题")) for c in cards)
            and len({c["问题"] for c in cards}) == len(cards))


def _outlines(tdir):
    """All planned cards must have exactly one currently validated outline."""
    if not _answers_ok(tdir):
        return []
    manifest_path = tdir.joinpath(*_ANSWERS_MANIFEST)
    manifest = _load_json(manifest_path)
    paths = sorted((tdir / _OUTLINES_DIR).glob("*.json"))
    seen, questions, good = set(), set(), []
    for path in paths:
        data = _load_json(path)
        if contract_errors(data):
            return []
        aid = data["article_id"]
        if aid in seen or data["问题"] in questions:
            return []
        seen.add(aid)
        questions.add(data["问题"])
        report = _load_json(tdir / "checks" / (aid + ".outline.json"))
        if not current_report(report, [path, manifest_path], "outline"):
            return []
        good.append(path)
    return good if questions == {c["问题"] for c in manifest["cards"]} else []


def _article_map(tdir):
    return {_load_json(p)["article_id"]: p for p in _outlines(tdir)}


def _draft_clean(tdir, chapter_md):
    outlines = _article_map(tdir)
    if chapter_md.stem not in outlines:
        return False
    report = _load_json(tdir / "checks" / (chapter_md.stem + ".draft.json"))
    return (current_report(report, [chapter_md, outlines[chapter_md.stem],
                                   tdir.joinpath(*_ANSWERS_MANIFEST)], "draft")
            and report.get("article_id") == chapter_md.stem)


def _lib_ok(tdir):
    data = _load_json(tdir.joinpath(*_LIB_MANIFEST))
    return (isinstance(data, dict) and nonempty(data.get("topic"))
            and isinstance(data.get("entries"), list) and bool(data["entries"])
            and isinstance(data.get("验收"), dict)
            and data["验收"].get("material_ok") is True
            and data["验收"].get("coverage_gaps") == [])


def _problems_ok(tdir):
    data = _load_json(tdir.joinpath(*_PROBLEM_LIST))
    return (isinstance(data, dict) and nonempty(data.get("topic"))
            and isinstance(data.get("problems"), list) and bool(data["problems"])
            and all(isinstance(p, dict) and nonempty(p.get("text") or p.get("问题"))
                    for p in data["problems"]))


def _drafts_ok(tdir):
    outlines = _article_map(tdir)
    chapters = _chapters(tdir)
    return (bool(outlines) and {p.stem for p in chapters} == set(outlines)
            and all(_draft_clean(tdir, p) for p in chapters))


def _qc_assets(tdir):
    paths, reasons = [], []
    if not _drafts_ok(tdir):
        return [], ["篇章集合不完整或 draft 机检未通过/已过期"]
    for aid, outline in _article_map(tdir).items():
        chapter = tdir / "chapters" / (aid + ".md")
        report_path = tdir / "qc" / (aid + ".json")
        render_path = tdir / "qc" / (aid + ".render.json")
        report, render = _load_json(report_path), _load_json(render_path)
        if not current_report(report, [chapter, outline, tdir.joinpath(*_ANSWERS_MANIFEST)], "tutorial"):
            reasons.append(f"{aid} 教程质检不通过、缺失或已过期")
        elif (report.get("article_id") != aid or not isinstance(report.get("dimensions"), dict)
              or set(report["dimensions"]) != {"可执行性", "可验证性", "覆盖完整性", "证据可靠性"}
              or any(not isinstance(d, dict) or d.get("status") not in ("pass", "not_applicable")
                     or (d.get("status") == "not_applicable" and not nonempty(d.get("reason")))
                     for d in report["dimensions"].values())):
            reasons.append(f"{aid} 有未通过或未核验的教程维度")
        if not current_report(render, [chapter], "render"):
            reasons.append(f"{aid} 成品渲染检查缺失、失败或已过期")
        paths += [report_path, render_path, chapter, outline,
                  tdir / "checks" / (aid + ".draft.json")]
    return paths, reasons


def collect_qc(tdir):
    tdir = Path(tdir)
    paths, reasons = _qc_assets(tdir)
    reports = [_load_json(p) for p in paths if p.suffix == ".json" and p.is_file()]
    warnings = [w for r in reports if isinstance(r, dict) for w in r.get("warnings", [])]
    result = diagnostic(reasons, warnings, article_ids=sorted(_article_map(tdir)))
    existing = [p for p in paths if p.is_file()]
    if existing:
        result = stamp(result, "qc-collection", existing + [tdir.joinpath(*_ANSWERS_MANIFEST)], __file__)
    write_json(tdir.joinpath(*_QC_REPORT), result)
    return result


def _qc_verdict(tdir):
    data = _load_json(tdir.joinpath(*_QC_REPORT))
    paths, reasons = _qc_assets(tdir)
    if (not reasons and current_report(data, paths, "qc-collection")
            and data.get("article_ids") == sorted(_article_map(tdir))):
        return data["status"]
    return None


def _gate_inputs(tdir, gate):
    paths = [tdir.joinpath(*_ANSWERS_MANIFEST)]
    paths += sorted((tdir / _OUTLINES_DIR).glob("*.json"))
    paths += sorted((tdir / _OUTLINES_DIR).glob("*.md"))
    paths += sorted((tdir / "checks").glob("*.outline.json"))
    if gate in ("l4", "publish"):
        paths += _chapters(tdir)
        paths += sorted((tdir / "checks").glob("*.draft.json"))
        paths += sorted((tdir / "qc").glob("*.json"))
        paths += sorted((tdir / "previews").glob("*.html"))
    return snapshots(paths)


def _gate_passed(tdir, conf, gate):
    if not conf.get(gate):
        return False
    if gate == "topic":
        return nonempty(conf[gate])
    try:
        return conf.get("_bindings", {}).get(gate) == _gate_inputs(tdir, gate)
    except OSError:
        return False


def stage_status(tdir):
    tdir = Path(tdir)
    conf = _load_confirmations(tdir)
    outlines, chs = _outlines(tdir), _chapters(tdir)
    checks = [_draft_clean(tdir, c) for c in chs]
    verdict = _qc_verdict(tdir)
    return {
        "stage0": {"satisfied": _lib_ok(tdir), "asset": "library/coverage-manifest.json"},
        "stage1": {"satisfied": _problems_ok(tdir), "asset": "problem_list.json"},
        "topic": {"satisfied": _gate_passed(tdir, conf, "topic"), "gate": "选题拍板", "confirmed": conf.get("topic")},
        "stage3": {"satisfied": _answers_ok(tdir), "asset": "answers/answers-manifest.json"},
        "stage4": {"satisfied": bool(outlines), "outlines": len(outlines), "asset": "outlines/*.json", "gate": "大纲确认", "gate_passed": _gate_passed(tdir, conf, "outline")},
        "stage5": {"satisfied": _drafts_ok(tdir), "chapters": len(chs), "checks_clean": sum(checks)},
        "stage6": {"satisfied": verdict is not None, "asset": "qc/report.json", "verdict": verdict},
        "delivered": {"satisfied": verdict is not None and all(_gate_passed(tdir, conf, g) for g in GATE_STAGE), "gates": ["L4人审", "发布"]},
        "confirmations": conf,
    }


def validate_next(tdir, target):
    tdir = Path(tdir)
    if target not in STAGES:
        return False, [f"未知阶段：{target}"]
    conf = _load_confirmations(tdir)
    idx, reasons = STAGES.index(target), []
    if idx >= STAGES.index("stage3") and not _gate_passed(tdir, conf, "topic"):
        reasons.append("硬闸门未过：选题未拍板")
    if idx >= STAGES.index("stage4") and not _answers_ok(tdir):
        reasons.append("answers/answers-manifest.json 缺失、未通过或已过期；先重新验证答案卡")
    if idx >= STAGES.index("stage5"):
        if not _outlines(tdir):
            reasons.append("大纲集合缺失、不完整或机检过期；检查 outlines/*.json 与 checks/*.outline.json")
        if not _gate_passed(tdir, conf, "outline"):
            reasons.append("硬闸门未过：大纲未确认或确认已过期")
    if idx >= STAGES.index("stage6") and not _drafts_ok(tdir):
        reasons.append("篇章集合不完整或 draft 机检未清零/已过期")
    if idx >= STAGES.index("delivered"):
        if _qc_verdict(tdir) is None:
            reasons.append("教程质检不通过、缺失或已过期；修复后重新 collect-qc")
        if not _gate_passed(tdir, conf, "l4"):
            reasons.append("硬闸门未过：L4 人审未签或已过期")
        if not _gate_passed(tdir, conf, "publish"):
            reasons.append("硬闸门未过：发布未确认或已过期")
    return not reasons, reasons


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
        conf.get("_bindings", {}).pop(g, None)
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
        if not nonempty(topic):
            return 2, {"error": "选题不可为空"}
        if topic != conf.get("topic"):
            for downstream in ("outline", "l4", "publish"):
                conf.pop(downstream, None)
                conf.get("_bindings", {}).pop(downstream, None)
        conf["topic"] = topic
        changed.append("topic")
    if gate is not None:
        if gate not in ("outline", "l4", "publish"):
            return 2, {"error": "topic 使用 --topic；其余闸门为 outline/l4/publish"}
        if gate == "outline" and (not _outlines(tdir) or not conf.get("topic")):
            return 1, {"error": "大纲或答案未通过当前验收，或选题未拍板"}
        if gate in ("l4", "publish") and (_qc_verdict(tdir) is None or not _gate_passed(tdir, conf, "outline")):
            return 1, {"error": "质检或大纲确认缺失/已过期"}
        if gate == "l4" and (not isinstance(l4_items, list) or len(set(l4_items)) < 4 or any(not nonempty(x) for x in l4_items)):
            return 2, {"error": "L4 至少记录证据、学习有效性、桌面、窄屏四项审阅结果"}
        if gate == "publish" and not _gate_passed(tdir, conf, "l4"):
            return 1, {"error": "发布前须完成当前稿 L4 人审"}
        conf[gate] = l4_items if gate == "l4" else True
        conf.setdefault("_bindings", {})[gate] = _gate_inputs(tdir, gate)
        for downstream in ({"outline": ("l4", "publish"), "l4": ("publish",), "publish": ()}[gate]):
            conf.pop(downstream, None)
            conf["_bindings"].pop(downstream, None)
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
    q = sub.add_parser("collect-qc", help="汇总当前各篇教程与成品检查，不执行人审")
    q.add_argument("--dir", required=True)
    args = ap.parse_args()

    if args.cmd == "collect-qc":
        sys.exit(finish(collect_qc(args.dir)))
    elif args.cmd == "status":
        print(json.dumps(stage_status(args.dir), ensure_ascii=False, indent=1))
    elif args.cmd == "next":
        ok, reasons = validate_next(args.dir, args.to)
        print(json.dumps({"can_proceed": ok, "reasons": reasons},
                         ensure_ascii=False, indent=1))
        sys.exit(0 if ok else 1)
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
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.exit(cli_error(exc))
