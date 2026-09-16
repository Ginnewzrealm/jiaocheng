import copy
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest
from pipeline_fixture import ROOT, build, answer, draft, flow, outline_module, render_markdown, tutorial_check
from tutorial_contract import contract_errors, current_report, diagnostic, prose, read_json, sha256, stamp, write_json


def test_real_outputs_flow_without_rewriting_reports(tmp_path):
    build(tmp_path)
    assert flow.validate_next(tmp_path, "delivered") == (True, [])
    assert flow.stage_status(tmp_path)["delivered"]["satisfied"]
    assert read_json(tmp_path / "checks/ch1.draft.json")["errors"] == []


@pytest.mark.parametrize("path", ["chapters/ch1.md", "outlines/大纲_Q1.json", "library/L1/print.md", "verification/print.log", "previews/ch1.html"])
def test_edits_invalidate_delivery(tmp_path, path):
    build(tmp_path)
    target = tmp_path / path
    target.write_text(target.read_text() + "\nchanged", encoding="utf-8")
    assert not flow.validate_next(tmp_path, "delivered")[0]
    assert not flow.stage_status(tmp_path)["delivered"]["satisfied"]


def test_missing_article_and_extra_outline_block(tmp_path):
    build(tmp_path)
    write_json(tmp_path / "outlines/extra.json", {})
    assert not flow.stage_status(tmp_path)["stage4"]["satisfied"]


@pytest.mark.parametrize("path,stage", [("problem_list.json", "stage1"), ("answers/answers-manifest.json", "stage3"), ("outlines/大纲_Q1.json", "stage4")])
def test_invalid_json_never_counts_as_asset(tmp_path, path, stage):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("not json")
    assert not flow.stage_status(tmp_path)[stage]["satisfied"]


def test_fabricated_claim_id_rejected(tmp_path):
    build(tmp_path, through="stage4")
    outline = read_json(tmp_path / "outlines/大纲_Q1.json")
    outline["小节"][0]["证据"] = ["C-ghost"]
    result = outline_module.check_outline(outline, read_json(tmp_path / "answers/answers-manifest.json"), str(tmp_path / "library"))
    assert any("C-ghost" in e for e in result["errors"])


def test_no_verification_is_not_verified_not_pass(tmp_path):
    build(tmp_path, through="stage5")
    result = tutorial_check.check_tutorial(tmp_path / "chapters/ch1.md", tmp_path / "outlines/大纲_Q1.json", tmp_path / "answers/answers-manifest.json", str(tmp_path / "library"))
    assert result["dimensions"]["可验证性"]["status"] == "not_verified"
    assert result["status"] == "fail"


def test_source_identity_and_authority(tmp_path):
    card = {"出处": [{"来源": "a", "url": "https://a.example/x", "定级": "high"},
                       {"来源": "b", "url": "https://a.example/y", "定级": "high"}]}
    assert answer.confidence_grade(card, str(tmp_path)) == "中"
    card["出处"][1]["url"] = "https://b.example/y"
    assert answer.confidence_grade(card) == "中"  # no-library ceiling
    for s in card["出处"]:
        s["original_source_id"] = "same-origin"
    assert answer.confidence_grade(card, str(tmp_path)) == "中"
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("unknown community source")
    assert answer.confidence_grade({"出处": [{"来源": "a.md"}, {"来源": "b.md"}]}, str(tmp_path)) == "低"


def test_snapshot_and_quote_mismatch_fail(tmp_path):
    build(tmp_path, through="stage3")
    card_path = tmp_path / "answers/print.json"
    card = read_json(card_path)
    card["claims"][0]["evidence"][0]["quote"] = "never in source"
    write_json(card_path, card)
    result = answer.validate_card(card_path, str(tmp_path / "library"))
    assert any("摘录" in e for e in result["errors"])


def test_cli_errors_have_nonzero_exit_and_json(tmp_path):
    card = tmp_path / "bad.json"
    write_json(card, {})
    result = subprocess.run([sys.executable, str(ROOT / "gin-answer/scripts/answer.py"), "validate", "--card", str(card)], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"]
    card.write_text("{")
    result = subprocess.run([sys.executable, str(ROOT / "gin-answer/scripts/answer.py"), "validate", "--card", str(card)], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"]


def test_markdown_code_is_not_prose_and_bad_structure_is_caught(tmp_path):
    text = '# 开始\n\n~~~python\n#### comment\nprint("让我们首先看看")\n~~~\n\n## 完成\n'
    assert "####" not in prose(text)
    result, _, _ = render_markdown.lint(text, tmp_path)
    assert result["errors"] == []
    bad, _, _ = render_markdown.lint('# 开始\n\n[跳转](#missing)\n\n```\nunclosed', tmp_path)
    assert any("锚点" in e for e in bad["errors"])
    assert any("未闭合" in e for e in bad["errors"])
    assert any("语言" in e for e in bad["errors"])


def test_markdown_tables_and_resources(tmp_path):
    result, _, _ = render_markdown.lint('| A | B |\n|---|---|\n| one | two | extra |\n\n![图](missing.png)', tmp_path)
    assert any("列数" in e for e in result["errors"])
    assert any("资源不存在" in e for e in result["errors"])


def test_protocol_copies_are_identical():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/sync_contracts.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("archetype", ["操作型", "排错型", "概念型", "对比型", "决策型", "实战型"])
def test_archetypes_keep_research_type_and_task_specific_contract(tmp_path, archetype):
    build(tmp_path, through="stage4")
    contract = read_json(tmp_path / "outlines/大纲_Q1.json")
    contract["tutorial_type"] = archetype
    if archetype == "概念型":
        for section in contract["小节"]:
            section.pop("步骤", None)
        assert any("练习" in e for e in contract_errors(contract))
        contract["练习"] = ["解释 print 的输出与返回值有何不同"]
    assert not contract_errors(contract)
    assert contract["类型"] == "方法型"


def test_rendered_anchor_targets_preview_not_source_directory(tmp_path):
    chapter = tmp_path / "source.md"
    chapter.write_text('# 示例\n\n[跳转](#结果)\n\n## 结果\n\n可用。[^C-1]\n\n[^C-1]: 来源。', encoding="utf-8")
    output = tmp_path / "preview/article.html"
    result = render_markdown.render_file(chapter, output)
    assert result["errors"] == []
    html = output.read_text()
    assert "<base " not in html
    assert 'id="结果"' in html and 'href="#结果"' in unquote(html)
    assert 'href="#fn1"' in html


def test_checker_change_invalidates_report(tmp_path):
    script = tmp_path / "checker.py"
    data = tmp_path / "input.md"
    script.write_text("version_one")
    data.write_text("input")
    report = stamp(diagnostic(), "test", [data], script)
    assert current_report(report, [data], "test")
    script.write_text("version_two")
    assert not current_report(report, [data], "test")


def test_rejected_legacy_outline_cli_fails(tmp_path):
    write_json(tmp_path / "outline.json", {"章节": []})
    write_json(tmp_path / "manifest.json", {"cards": []})
    result = subprocess.run([sys.executable, str(ROOT / "gin-outline/scripts/outline.py"), "check",
                             "--outline", str(tmp_path / "outline.json"), "--manifest", str(tmp_path / "manifest.json")],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "fail"


def test_checkers_cli_end_to_end(tmp_path):
    build(tmp_path)
    commands = [
        ["gin-answer/scripts/answer.py", "manifest", "--dir", str(tmp_path / "answers"), "--topic", "t", "--library", str(tmp_path / "library")],
        ["gin-outline/scripts/outline.py", "check", "--outline", str(tmp_path / "outlines/大纲_Q1.json"), "--manifest", str(tmp_path / "answers/answers-manifest.json"), "--library", str(tmp_path / "library"), "--output", str(tmp_path / "checks/ch1.outline.json")],
        ["gin-draft/scripts/draft.py", "check", "--file", str(tmp_path / "chapters/ch1.md"), "--outline", str(tmp_path / "outlines/大纲_Q1.json"), "--manifest", str(tmp_path / "answers/answers-manifest.json"), "--library", str(tmp_path / "library"), "--output", str(tmp_path / "checks/ch1.draft.json")],
        ["gin-qc/scripts/tutorial_check.py", "--file", str(tmp_path / "chapters/ch1.md"), "--outline", str(tmp_path / "outlines/大纲_Q1.json"), "--manifest", str(tmp_path / "answers/answers-manifest.json"), "--library", str(tmp_path / "library"), "--verification", str(tmp_path / "verification/print.json"), "--output", str(tmp_path / "qc/ch1.json")],
        ["gin-qc/scripts/render_markdown.py", "--file", str(tmp_path / "chapters/ch1.md"), "--html", str(tmp_path / "previews/ch1.html"), "--output", str(tmp_path / "qc/ch1.render.json")],
        ["xiejiaocheng/scripts/flow_controller.py", "collect-qc", "--dir", str(tmp_path)],
    ]
    for command in commands:
        command[0] = str(ROOT / command[0])
        result = subprocess.run([sys.executable] + command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    assert flow.cmd_confirm(tmp_path, gate="outline")[0] == 0
    assert flow.cmd_confirm(tmp_path, gate="l4", l4_items=["证据:test", "学习:test", "桌面:test", "窄屏:test"])[0] == 0
    assert flow.cmd_confirm(tmp_path, gate="publish")[0] == 0
    assert flow.validate_next(tmp_path, "delivered")[0]
