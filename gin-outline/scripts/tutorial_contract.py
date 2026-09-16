"""Tutorial protocol v3. Source of the self-contained copies in each skill.

Edit this file, then run scripts/sync_contracts.py. Standard library only.
"""
import hashlib
import json
import re
from pathlib import Path

VERSION = 3
ARCHETYPES = ("操作型", "概念型", "排错型", "对比型", "决策型", "实战型")
STATUSES = ("pass", "minor", "fail")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshots(paths):
    return [{"path": str(p), "sha256": sha256(p)}
            for p in sorted({Path(p).resolve() for p in paths})]


def current_snapshots(items, required=()):
    if not isinstance(items, list) or not items:
        return False
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not nonempty(item.get("path")):
            return False
        path = Path(item["path"])
        if not path.is_absolute() or str(path.resolve()) in seen:
            return False
        try:
            if sha256(path) != item.get("sha256"):
                return False
        except OSError:
            return False
        seen.add(str(path.resolve()))
    return {str(Path(p).resolve()) for p in required} <= seen


def diagnostic(errors=(), warnings=(), **extra):
    errors, warnings = list(errors), list(warnings)
    return {**extra, "schema_version": VERSION, "errors": errors,
            "warnings": warnings, "error_count": len(errors),
            "warning_count": len(warnings),
            "status": "fail" if errors else "minor" if warnings else "pass"}


def stamp(result, checker, paths, script):
    result = dict(result)
    result.update(schema_version=VERSION, inputs=snapshots(paths), checker={
        "name": checker, "version": VERSION,
        "files": snapshots(Path(script).resolve().parent.glob("*.py")),
    })
    return result


def current_report(report, required=(), checker=None):
    if not isinstance(report, dict) or report.get("schema_version") != VERSION:
        return False
    errors = report.get("errors")
    warnings = report.get("warnings")
    tool = report.get("checker", {})
    return (isinstance(errors, list) and not errors
            and isinstance(warnings, list)
            and type(report.get("error_count")) is int and report["error_count"] == 0
            and report.get("warning_count") == len(warnings)
            and report.get("status") in ("pass", "minor")
            and isinstance(tool, dict) and tool.get("version") == VERSION
            and (checker is None or tool.get("name") == checker)
            and current_snapshots(tool.get("files"))
            and current_snapshots(report.get("inputs"), required))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finish(report, output=None):
    if output:
        write_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("errors") or report.get("status") == "fail" else 0


def cli_error(exc):
    print(json.dumps(diagnostic([f"输入或工具错误：{exc}"]), ensure_ascii=False))
    return 2


def inside(root, name):
    if not nonempty(name) or Path(name).is_absolute():
        raise ValueError(f"必须使用资料库内相对文件路径：{name}")
    root = Path(root).resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError(f"文件不存在或越出资料库：{name}")
    return path


def prose(text):
    """Remove fenced code and HTML comments while preserving line numbers.

    Supports backtick/tilde fences (including quoted/list-indented fences).
    Lint handles malformed fences; no execution or HTML interpretation occurs.
    """
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.S)
    lines, fence = [], None
    for line in text.splitlines():
        stripped = re.sub(r"^\s*(?:>\s*)*", "", line)
        match = re.match(r"(`{3,}|~{3,})(.*)$", stripped)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            lines.append("")
        elif match:
            fence = match[1]
            lines.append("")
        elif line.startswith("    ") or line.startswith("\t"):
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines)


def sources_of(card):
    return card.get("出处", []) if isinstance(card, dict) else []


def source_paths(card, library):
    return [inside(library, s["来源"]) for s in sources_of(card)
            if isinstance(s, dict) and (card.get("schema_version") == VERSION
                or str(s.get("来源", "")).endswith((".md", ".markdown")))]


def checked_record(record):
    return (isinstance(record, dict) and record.get("status") == "verified"
            and all(nonempty(record.get(k)) for k in ("by", "at", "method")))


def claim_errors(card, library=None):
    """Check recorded source support, not the truth of the author's judgment."""
    errors = []
    sources = sources_of(card)
    if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
        return ["出处须是对象数组"]
    source_map = {}
    for src in sources:
        sid = src.get("source_id")
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in source_map:
            errors.append("source_id 缺失、重复或非法")
            continue
        source_map[sid] = src
        if not nonempty(src.get("original_source_id")):
            errors.append(f"{sid} 缺 original_source_id")
        if not library:
            errors.append(f"{sid} 缺资料库，不能核对证据快照")
            continue
        try:
            path = inside(library, src.get("来源"))
            if sha256(path) != src.get("sha256"):
                errors.append(f"{sid} 来源快照哈希不符")
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    claims = card.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["claims 必须是非空结论账本"]
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim 必须是对象")
            continue
        cid = claim.get("claim_id")
        if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in seen:
            errors.append("claim_id 缺失、重复或非法")
            continue
        seen.add(cid)
        for field in ("statement", "claim_type", "scope"):
            if not nonempty(claim.get(field)):
                errors.append(f"{cid} 缺 {field}")
        if not isinstance(claim.get("conflicts"), list):
            errors.append(f"{cid} conflicts 须是数组，未发现冲突填 []")
        elif claim["conflicts"]:
            errors.append(f"{cid} 有未解决冲突，不能作为达标结论")
        verification = claim.get("verification", {})
        if not isinstance(verification, dict) or not checked_record(verification.get("support")):
            errors.append(f"{cid} 缺原文支持结论的核验记录")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{cid} 缺 evidence")
            continue
        for ev in evidence:
            if not isinstance(ev, dict) or ev.get("source_id") not in source_map:
                errors.append(f"{cid} 引用了不存在的 source_id")
                continue
            if not all(nonempty(ev.get(k)) for k in ("quote", "locator")):
                errors.append(f"{cid} 缺 quote/locator")
                continue
            if library:
                try:
                    path = inside(library, source_map[ev["source_id"]].get("来源"))
                    if ev["quote"] not in path.read_text(encoding="utf-8"):
                        errors.append(f"{cid} 原文摘录在快照中不存在")
                except (ValueError, OSError) as exc:
                    errors.append(str(exc))
    return errors


def contract_errors(outline):
    if not isinstance(outline, dict):
        return ["大纲必须是对象"]
    errors = []
    if outline.get("schema_version") != VERSION:
        errors.append("大纲须迁移为 schema_version: 3；旧件不可冒充已验证")
    aid = outline.get("article_id")
    if not isinstance(aid, str) or not ID.fullmatch(aid):
        errors.append("article_id 必须是稳定的字母/数字/连字符标识")
    if outline.get("tutorial_type") not in ARCHETYPES:
        errors.append("tutorial_type 不属于六种教程原型")
    for field in ("问题", "标题", "写给", "读完能", "适用范围"):
        if not nonempty(outline.get(field)):
            errors.append(f"缺 {field}")
    for field in ("前置条件", "失败边界", "交付物"):
        values = outline.get(field)
        if not isinstance(values, list) or any(not nonempty(v) for v in values):
            errors.append(f"{field} 须是文本数组")
        elif field != "前置条件" and not values:
            errors.append(f"{field} 不可为空（不适用时说明原因）")
    if not isinstance(outline.get("环境"), dict) or not outline["环境"] or any(
            not nonempty(v) for v in outline.get("环境", {}).values()):
        errors.append("环境须声明版本/平台或适用人群/证据日期等条件")
    criteria = outline.get("成功标准")
    criteria_ids = set()
    if not isinstance(criteria, list) or not criteria:
        errors.append("缺可验证的成功标准")
    else:
        for item in criteria:
            if not isinstance(item, dict) or any(not nonempty(item.get(k)) for k in
                    ("criterion_id", "描述", "验证方法", "预期结果")):
                errors.append("成功标准缺 criterion_id/描述/验证方法/预期结果")
            elif item["criterion_id"] in criteria_ids:
                errors.append("criterion_id 重复")
            else:
                criteria_ids.add(item["criterion_id"])
    sections = outline.get("小节")
    if not isinstance(sections, list) or not sections:
        return errors + ["小节必须是非空数组"]
    section_ids, step_ids = set(), set()
    titles = set()
    for sec in sections:
        if not isinstance(sec, dict):
            errors.append("小节必须是对象")
            continue
        sid = sec.get("section_id")
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in section_ids:
            errors.append("section_id 缺失、重复或非法")
        else:
            section_ids.add(sid)
        for field in ("标题", "干什么"):
            if not nonempty(sec.get(field)):
                errors.append(f"{sid} 缺 {field}")
        if nonempty(sec.get("标题")):
            if sec["标题"] in titles:
                errors.append("小节标题重复，正文定位不明确")
            titles.add(sec["标题"])
        if not isinstance(sec.get("证据"), list) or not sec["证据"] or any(
                not nonempty(c) for c in sec.get("证据", [])):
            errors.append(f"{sid} 缺结论 ID 数组")
        steps = sec.get("步骤", [])
        if not isinstance(steps, list):
            errors.append(f"{sid} 步骤必须是数组")
            continue
        for step in steps:
            if not isinstance(step, dict) or any(not nonempty(step.get(k)) for k in
                    ("step_id", "动作", "预期结果", "验证方法", "失败处理")):
                errors.append(f"{sid} 步骤缺动作/预期结果/验证方法/失败处理")
                continue
            if not ID.fullmatch(step["step_id"]) or step["step_id"] in step_ids:
                errors.append("step_id 重复或非法")
            step_ids.add(step["step_id"])
    if outline.get("tutorial_type") in ("操作型", "排错型") and not step_ids:
        errors.append("操作型/排错型至少需要一个完整步骤")
    if outline.get("tutorial_type") == "概念型" and not (
            isinstance(outline.get("练习"), list) and outline["练习"]
            and all(nonempty(x) for x in outline["练习"])):
        errors.append("概念型缺迁移练习")
    return errors


def matching_card(outline, manifest):
    if not isinstance(manifest, dict):
        return None
    cards = manifest.get("cards", manifest.get("达标卡", []))
    if not isinstance(cards, list):
        return None
    found = [c for c in cards if isinstance(c, dict) and c.get("问题") == outline.get("问题")]
    return found[0] if len(found) == 1 else None


def reference_errors(outline, card):
    if card is None:
        return ["卡片不存在或问题重复"]
    ids = {c.get("claim_id") for c in card.get("claims", []) if isinstance(c, dict)}
    return [f"未知结论 ID：{cid}" for s in outline.get("小节", []) if isinstance(s, dict)
            for cid in (s.get("证据") if isinstance(s.get("证据"), list) else [])
            if isinstance(cid, str) and cid not in ids]


def body_reference_errors(text, outline, card):
    clean = prose(text)
    body = re.sub(r"^\[\^[^\]]+\]:.*$", "", clean, flags=re.M)
    used = set(re.findall(r"\[\^([A-Za-z0-9_-]+)\]", body))
    known = {c["claim_id"] for c in card.get("claims", [])}
    expected = {c for s in outline["小节"] for c in s["证据"]}
    errors = [f"正文引用不存在的结论：{c}" for c in sorted(used - known)]
    errors += [f"正文缺关键结论引用：{c}" for c in sorted(expected - used)]
    titles = re.findall(r"^##\s+(.+?)\s*$", clean, flags=re.M)
    if titles != [s["标题"] for s in outline["小节"]]:
        errors.append("正文 H2 与大纲小节标题/顺序不一致")
    bodies = re.split(r"^##\s+.+$", body, flags=re.M)[1:]
    for sec, chunk in zip(outline["小节"], bodies):
        refs = set(re.findall(r"\[\^([A-Za-z0-9_-]+)\]", chunk))
        for cid in sec["证据"]:
            if cid not in refs:
                errors.append(f"{sec['section_id']} 缺本节结论引用：{cid}")
    return errors
