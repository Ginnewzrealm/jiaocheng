"""Synthetic integration scenario, not a claimed real-world writing baseline."""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for skill in ("gin-answer", "gin-outline", "gin-draft", "gin-qc", "xiejiaocheng"):
    sys.path.insert(0, str(ROOT / skill / "scripts"))
from tutorial_contract import diagnostic, sha256, stamp, write_json
import answer
import outline as outline_module
import draft
import tutorial_check
import render_markdown
import flow_controller as flow


def build(work, through="delivered", article_id="ch1", question="Q1", topic="t"):
    work = Path(work)
    library = work / "library"
    source = library / "L1/print.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("Synthetic test source. print('ready') writes ready followed by a newline.\n", encoding="utf-8")
    write_json(library / "coverage-manifest.json", {
        "topic": topic, "entries": [{"path": str(source)}],
        "验收": {"material_ok": True, "coverage_gaps": []}})
    write_json(work / "problem_list.json", {"topic": topic, "problems": [{"text": question}]})
    if through == "stage1":
        return work
    flow.cmd_confirm(work, topic=topic)
    card = {"schema_version": 3, "问题": question, "类型": "方法型", "一句话答案": "运行 print 即可打印文字",
        "置信度": "中", "状态": "达标", "争议点": [], "适用边界": ["本地 Python 3"],
        "出处": [{"source_id": "S-1", "来源": "L1/print.md", "定级": "high",
                  "url": "https://example.invalid/fixture", "original_source_id": "fixture:print",
                  "sha256": sha256(source)}],
        "claims": [{"claim_id": "C-1", "statement": "print 可打印 ready", "claim_type": "可复现行为",
                    "scope": "Python 3", "conflicts": [],
                    "evidence": [{"source_id": "S-1", "locator": "第1行", "quote": "print('ready') writes ready followed by a newline."}],
                    "verification": {"support": {"status": "verified", "by": "synthetic-fixture", "at": "2026-09-16", "method": "核对测试快照"}}}]}
    card_path = work / "answers/print.json"
    write_json(card_path, card)
    manifest = answer.build_manifest([card], topic, str(library))
    manifest = stamp(manifest, "answers-manifest", [card_path, source], answer.__file__)
    manifest_path = work / "answers/answers-manifest.json"
    write_json(manifest_path, manifest)
    if through == "stage3":
        return work
    contract = {"schema_version": 3, "article_id": article_id, "问题": question,
        "标题": "打印一次 ready", "类型": "方法型", "tutorial_type": "操作型",
        "写给": "已装 Python 3、准备验证终端输出的人", "读完能": "能在终端打印 ready",
        "前置条件": ["安装 Python 3"], "适用范围": "本地终端", "环境": {"Python": "3", "平台": sys.platform},
        "成功标准": [{"criterion_id": "K-1", "描述": "打印结果正确", "验证方法": "检查标准输出", "预期结果": "标准输出为 ready"}],
        "失败边界": ["找不到 python3 时检查安装和 PATH"], "交付物": ["终端输出记录"],
        "素材": ["L1/print.md"], "小节": [
            {"section_id": "prepare", "标题": "准备终端", "干什么": "确认前置条件", "证据": ["C-1"]},
            {"section_id": "run", "标题": "运行并检查", "干什么": "执行命令并验证", "证据": ["C-1"], "构件": "代码块",
             "步骤": [{"step_id": "run-print", "动作": "运行打印命令", "预期结果": "标准输出为 ready", "验证方法": "检查标准输出", "失败处理": "找不到 python3 时检查安装和 PATH"}]},
            {"section_id": "save", "标题": "保存结果", "干什么": "带走记录", "证据": ["C-1"]}]}
    outline_path = work / "outlines/大纲_Q1.json"
    write_json(outline_path, contract)
    check = outline_module.check_outline(contract, manifest, str(library))
    assert not check["errors"], check
    write_json(work / f"checks/{article_id}.outline.json", stamp(check, "outline", [outline_path, manifest_path, source], outline_module.__file__))
    if through == "stage4":
        return work
    code, payload = flow.cmd_confirm(work, gate="outline")
    assert code == 0, payload
    text = '''# 打印一次 ready
写给：已装 Python 3、准备验证终端输出的人。
读完能在终端打印 ready。

## 准备终端
安装 Python 3。print 可以输出文字。[^C-1]

## 运行并检查
<!-- step:run-print -->
1. 运行打印命令。[^C-1]

```bash
python3 -c "print('ready')"
```

预期结果：标准输出为 ready。
验证方法：检查标准输出。
失败处理：找不到 python3 时检查安装和 PATH。

## 保存结果
print 输出文字后退出。[^C-1]

- [ ] 保存终端输出记录。

[^C-1]: [测试用受控来源](https://example.invalid/fixture)。
'''
    chapter = work / f"chapters/{article_id}.md"
    chapter.parent.mkdir(parents=True, exist_ok=True)
    chapter.write_text(text, encoding="utf-8")
    check = draft.check_chapter(text, library=str(library), outline=contract, manifest=manifest)
    assert not check["errors"], check
    check["article_id"] = article_id
    write_json(work / f"checks/{article_id}.draft.json", stamp(check, "draft", [chapter, outline_path, manifest_path, source], draft.__file__))
    if through == "stage5":
        return work
    log = work / "verification/print.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([sys.executable, "-c", "print('ready')"], capture_output=True, text=True, check=True)
    log.write_text(run.stdout, encoding="utf-8")
    record = work / "verification/print.json"
    write_json(record, {"schema_version": 3, "article_id": article_id, "document_sha256": sha256(chapter),
        "outline_sha256": sha256(outline_path), "environment": contract["环境"], "checks": [{
            "criterion_id": "K-1", "status": "pass", "observed": run.stdout, "by": "automated-test", "at": "2026-09-16",
            "method": "Python 3 subprocess, assert stdout == ready newline", "log": "print.log", "sha256": sha256(log)}]})
    assert run.stdout == "ready\n"
    result = tutorial_check.check_tutorial(chapter, outline_path, manifest_path, str(library), record)
    assert not result["errors"], result
    write_json(work / f"qc/{article_id}.json", result)
    result = render_markdown.render_file(chapter, work / f"previews/{article_id}.html")
    assert not result["errors"], result
    write_json(work / f"qc/{article_id}.render.json", result)
    result = flow.collect_qc(work)
    assert not result["errors"], result
    if through == "stage6":
        return work
    # Synthetic signed review solely for exercising gate mechanics.
    for gate in ("l4", "publish"):
        code, payload = flow.cmd_confirm(work, gate=gate, l4_items=["证据:test", "学习:test", "桌面:test", "窄屏:test"])
        assert code == 0, payload
    return work
