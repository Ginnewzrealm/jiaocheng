#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""output_renderer.py — 生成 problem_list.json / problem_list.md / audit_report.json。"""

import os

from common import ensure_dir, now_iso, save_json


def render_markdown(topic, problems, coverage_matrix):
    """生成 Markdown 格式问题清单。"""
    lines = []
    lines.append(f"# {topic} — 真问题清单")
    lines.append("")
    lines.append(f"> 生成时间：{now_iso()[:10]}")
    lines.append("")

    # 按视角分组
    grouped = {}
    for p in problems:
        per = p.get("retrieval_perspective", "其他")
        grouped.setdefault(per, []).append(p)

    for perspective, items in grouped.items():
        lines.append(f"## {perspective}视角")
        lines.append("")
        lines.append("| ID | 问题 | 子维度 | 来源数 | 状态 |")
        lines.append("|---|---|---|---|---|")
        for p in items:
            lines.append(
                f"| {p['id']} | {p['text']} | {p.get('sub_dimension', '')} | "
                f"{p.get('source_count', 0)} | {p.get('status', '')} |"
            )
        lines.append("")

    # 16 格覆盖度
    lines.append("## 16 格覆盖度")
    lines.append("")
    for perspective, subs in coverage_matrix.items():
        for sub, count in subs.items():
            mark = "✅" if count > 0 else "❌"
            lines.append(f"- {perspective} / {sub}: {mark} ({count})")
    lines.append("")

    # 详细问题
    lines.append("## 详细问题")
    lines.append("")
    for p in problems:
        lines.append(f"### {p['id']} {p['text']}")
        lines.append(f"- **原始文本**：{p.get('original', '')}")
        lines.append(f"- **视角 / 子维度**：{p.get('retrieval_perspective', '')} / {p.get('sub_dimension', '')}")
        lines.append(f"- **状态**：{p.get('status', '')}")
        lines.append(f"- **总频次 / 来源数**：{p.get('total_frequency', 0)} / {p.get('source_count', 0)}")
        if p.get("duplicates"):
            lines.append(f"- **合并的近似问题**：{', '.join(p['duplicates'])}")
        if p.get("sources"):
            lines.append("- **来源**：")
            for s in p["sources"]:
                lines.append(f"  - [{s.get('type', 'unknown')}] {s.get('url', '')} (频次 {s.get('frequency', 1)})")
        lines.append("")

    return "\n".join(lines)


def render_outputs(topic, problems, pending_validation, audit, output_dir):
    """生成全部输出文件。"""
    ensure_dir(output_dir)

    generated_at = now_iso()

    problem_list = {
        "topic": topic,
        "generated_at": generated_at,
        "exit_reason": audit.get("exit_reason", "saturated"),
        "retrieval_rounds": audit.get("retrieval_rounds", 1),
        "problems": problems,
        "pending_validation": pending_validation,
    }

    audit_report = {
        "topic": topic,
        "generated_at": generated_at,
        **audit,
    }

    json_path = os.path.join(output_dir, "problem_list.json")
    md_path = os.path.join(output_dir, "problem_list.md")
    audit_path = os.path.join(output_dir, "audit_report.json")

    save_json(json_path, problem_list)
    save_json(audit_path, audit_report)

    coverage_matrix = audit.get("perspective_coverage", {})
    md = render_markdown(topic, problems, coverage_matrix)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    return {
        "problem_list_json": json_path,
        "problem_list_md": md_path,
        "audit_report_json": audit_path,
    }


def main():
    import sys
    import json
    if len(sys.argv) < 4:
        print("用法: python3 output_renderer.py <topic> <problems-json> <audit-json> <output-dir>")
        sys.exit(1)
    topic = sys.argv[1]
    problems = json.loads(sys.argv[2])
    audit = json.loads(sys.argv[3])
    output_dir = sys.argv[4]
    pending = []
    out = render_outputs(topic, problems, pending, audit, output_dir)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
