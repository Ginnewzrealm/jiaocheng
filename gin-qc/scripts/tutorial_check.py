#!/usr/bin/env python3
"""Check tutorial contracts, claims and recorded outcomes independently of style."""
import argparse
import re
import sys
from pathlib import Path

from tutorial_contract import (VERSION, body_reference_errors, claim_errors, cli_error,
    contract_errors, current_report, diagnostic, finish, inside, matching_card,
    nonempty, prose, read_json, reference_errors, sha256, source_paths, stamp)
from qc import check_humanity
from render_markdown import lint


def outcomes(record, outline, document, outline_path, record_path):
    """Validate a recorded observation; never execute commands or invent results."""
    errors, paths = [], []
    if not isinstance(record, dict):
        return ["尚未提供成功标准的实际核验记录"], [], "not_verified"
    if (record.get("schema_version") != VERSION or record.get("article_id") != outline["article_id"]
            or record.get("document_sha256") != sha256(document)
            or record.get("outline_sha256") != sha256(outline_path)
            or record.get("environment") != outline["环境"]):
        return ["核验记录与当前正文、大纲或环境不匹配"], [], "not_verified"
    checks = record.get("checks")
    if not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks):
        return ["核验 checks 必须是对象数组"], [], "not_verified"
    expected = {c["criterion_id"] for c in outline["成功标准"]}
    if {c.get("criterion_id") for c in checks} != expected or len(checks) != len(expected):
        errors.append("核验记录未一一覆盖成功标准")
    state = "pass"
    for check in checks:
        if check.get("status") != "pass":
            errors.append(f"成功标准尚未通过：{check.get('criterion_id')}")
            state = "fail" if check.get("status") == "fail" else "not_verified"
            continue
        if not all(nonempty(check.get(k)) for k in ("observed", "by", "at", "method", "log", "sha256")):
            errors.append("已通过的核验缺观察结果、检查者、时间、方法或日志")
            continue
        try:
            log = inside(Path(record_path).parent, check["log"])
            if sha256(log) != check["sha256"]:
                errors.append("核验日志哈希不符")
            else:
                paths.append(log)
        except ValueError as exc:
            errors.append(str(exc))
    return errors, paths, state if not errors or state != "pass" else "fail"


def check_tutorial(document, outline_path, manifest_path, library, verification=None):
    text = Path(document).read_text(encoding="utf-8")
    outline, manifest = read_json(outline_path), read_json(manifest_path)
    contract = contract_errors(outline)
    if contract:
        return stamp(diagnostic(contract), "tutorial", [document, outline_path, manifest_path], __file__)
    card = matching_card(outline, manifest)
    evidence = reference_errors(outline, card)
    if card:
        evidence += claim_errors(card, library)
        if card.get("状态") != "达标":
            evidence.append("答案卡未达标")
    if not current_report(manifest, checker="answers-manifest"):
        evidence.append("答案 manifest 未验收或已过期")
    coverage = body_reference_errors(text, outline, card) if card and not evidence else []
    clean = prose(text)
    execution = []
    for sec in outline["小节"]:
        for step in sec.get("步骤", []):
            marker = f"<!-- step:{step['step_id']} -->"
            if text.count(marker) != 1:
                execution.append(f"步骤标记缺失或重复：{step['step_id']}")
                continue
            chunk = re.split(r"<!-- step:|\n##\s", text.split(marker, 1)[1], maxsplit=1)[0]
            for field in ("动作", "预期结果", "验证方法", "失败处理"):
                if step[field] not in chunk:
                    execution.append(f"{step['step_id']} 正文缺大纲中的{field}")
    for field in ("前置条件", "失败边界", "交付物", "练习"):
        for value in outline.get(field, []):
            if value not in clean:
                coverage.append(f"正文缺{field}：{value}")
    for criterion in outline["成功标准"]:
        if criterion["预期结果"] not in text:
            coverage.append(f"正文缺成功判据：{criterion['criterion_id']}")
    result_errors, logs, state = outcomes(read_json(verification) if verification else None,
                                        outline, document, outline_path, verification)
    render, resources, _ = lint(text, Path(document).parent)
    style = check_humanity(text, tutorial_type=outline["tutorial_type"])
    dims = {
        "可执行性": {"status": "fail" if execution else "pass" if any(s.get("步骤") for s in outline["小节"]) else "not_applicable",
                    "reason": "按步骤契约检查" if any(s.get("步骤") for s in outline["小节"]) else "本原型以理解或决策产物验收，未声明操作步骤", "errors": execution},
        "可验证性": {"status": state, "errors": result_errors},
        "覆盖完整性": {"status": "fail" if coverage else "pass", "errors": coverage},
        "证据可靠性": {"status": "fail" if evidence else "pass", "errors": evidence,
                       "reason": "核对来源快照和已记录的原文支持审阅；语义判断仍须人工复核"},
    }
    errors = execution + result_errors + coverage + evidence + render["errors"]
    if style["status"] == "fail":
        errors += style["errors"] or ["风格检查低于最低分数"]
    warnings = render["warnings"] + style["warnings"]
    result = diagnostic(errors, warnings, article_id=outline["article_id"], dimensions=dims,
                        style=style, render=render, review_items=[
                            "关键断言是否全部登记且原文确实支持", "读者是否无需猜测就能完成目标",
                            "术语与边界是否解释充分", "桌面与窄屏成品是否清晰可读"])
    paths = [document, outline_path, manifest_path] + logs + resources
    if verification:
        paths.append(verification)
    if card and not evidence:
        paths += source_paths(card, library)
    return stamp(result, "tutorial", paths, __file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--outline", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--library", required=True)
    ap.add_argument("--verification", help="实际核验记录；不提供时明确报 not_verified")
    ap.add_argument("--output")
    args = ap.parse_args()
    return finish(check_tutorial(args.file, args.outline, args.manifest, args.library, args.verification), args.output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.exit(cli_error(exc))
