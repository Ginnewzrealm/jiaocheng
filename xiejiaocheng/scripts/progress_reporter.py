#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Progress Checklist 渲染器（xiejiaocheng 宏观/微观仪表盘）。

依据《AI技能进度条设计指南》v1.0：
- §3.1/§6.2 宏观层：5 用户阶段仪表盘（9 内部 stage 聚合）
- §3.2 微观层：阶段内 micro-checklist，动作 → 产出物命名（§11.4）
- §3.3 状态：- [✓] / - [ ] + ← 当前
- §3.5 阻塞提示："你可以：" 选项块

本模块无状态：所有数据从 flow_controller.stage_status() 的返回推导，
"rolled_back_to"（软回环锚点）存于 confirmations.json，由 rollback/confirm 维护。
"""
# 内部 stage 的线性顺序：直接取 flow_controller 的 STAGES（单一事实源，
# flow_controller 只在函数内懒加载本模块，无循环导入）
from flow_controller import STAGES as STAGE_ORDER  # noqa: E402

_TRACKED = [s for s in STAGE_ORDER if s != "init"]

STAGE_TO_PHASE = {
    "stage0": 1, "stage1": 2, "topic": 2, "stage3": 3,
    "stage4": 4, "stage5": 4, "stage6": 5, "delivered": 5,
}

PHASE_NAMES = {
    1: "阶段 1/5：扒资料",
    2: "阶段 2/5：找问题",
    3: "阶段 3/5：找答案·选题",
    4: "阶段 4/5：结构与写作",
    5: "阶段 5/5：质检与交付",
}

# 每阶段 micro-checklist。命名规范：动作 → 产出物（指南 §11.4）；
# 标签四选：自动 / 需确认 / 硬闸门 / 可回环（误区 3：硬闸门不混 需确认）；
# done(st) 从 stage_status 推导该步是否已完成。
MICRO_STEPS = {
    "stage0": [
        {"name": "认账资料库 → coverage-manifest.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage0")},
        {"name": "跑 source-scan → sources.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage0")},
        {"name": "跑 harvest → Markdown 资料库", "tags": ["自动"],
         "done": lambda st: _s(st, "stage0")},
        {"name": "验收素材量 → coverage-manifest.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage0")},
        {"name": "汇报资料盘点 → progress.md", "tags": ["需确认"],
         "done": lambda st: _s(st, "stage0")},
    ],
    "stage1": [
        {"name": "认账问题清单 → problem_list.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage1")},
        {"name": "跑 gin-question → problem_list.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage1")},
        {"name": "16 格覆盖审计 → audit_report.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage1")},
        {"name": "汇报问题盘点 → 候选选题", "tags": ["需确认"],
         "done": lambda st: _s(st, "stage1")},
    ],
    "topic": [
        {"name": "读问题清单 → 候选选题", "tags": ["自动"],
         "done": lambda st: _s(st, "stage1")},
        {"name": "展示候选选题 → 对比表", "tags": ["需确认"],
         "done": lambda st: bool(st["confirmations"].get("topic"))},
        {"name": "用户拍板 → confirmations.json:topic", "tags": ["硬闸门", "可回环"],
         "done": lambda st: bool(st["confirmations"].get("topic"))},
    ],
    "stage3": [
        {"name": "校验选题闸门 → 放行/拦截", "tags": ["自动"],
         "done": lambda st: bool(st["confirmations"].get("topic"))},
        {"name": "分批跑 gin-answer → 答案卡.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage3")},
        {"name": "批边界汇报 → 置信摘要", "tags": ["需确认"],
         "done": lambda st: _s(st, "stage3")},
        {"name": "汇总 → answers-manifest.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage3")},
    ],
    "stage4": [
        {"name": "读 manifest+资料库 → 大纲原料", "tags": ["自动"],
         "done": lambda st: _s(st, "stage4")},
        {"name": "跑 gin-outline → 大纲.md/json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage4")},
        {"name": "机检 8 条 → 缺口清单", "tags": ["自动"],
         "done": lambda st: _s(st, "stage4")},
        {"name": "展示大纲 → 章节结构", "tags": ["需确认"],
         "done": lambda st: bool(st["confirmations"].get("outline"))},
        {"name": "用户确认大纲 → confirmations.json:outline",
         "tags": ["硬闸门", "可回环"],
         "done": lambda st: bool(st["confirmations"].get("outline"))},
    ],
    "stage5": [
        {"name": "取一章大纲 → 章构件任务", "tags": ["自动"],
         "done": lambda st: _s(st, "stage5")},
        {"name": "跑 gin-draft → chapters/*.md", "tags": ["自动"],
         "done": lambda st: _s(st, "stage5")},
        {"name": "章机检清零 → checks/*.draft.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage5")},
        {"name": "汇报章节进度 → 批内摘要", "tags": ["需确认"],
         "done": lambda st: _s(st, "stage5")},
    ],
    "stage6": [
        {"name": "收集各章+报告 → 质检输入", "tags": ["自动"],
         "done": lambda st: _s(st, "stage6")},
        {"name": "跑 gin-qc → qc/report.json", "tags": ["自动"],
         "done": lambda st: _s(st, "stage6")},
        {"name": "汇报 L4 人审项 → 六项清单", "tags": ["需确认"],
         "done": lambda st: _s(st, "stage6")},
    ],
    "delivered": [
        {"name": "L4 四项人审 → confirmations.json:l4", "tags": ["硬闸门"],
         "done": lambda st: bool(st["confirmations"].get("l4"))},
        {"name": "用户确认发布 → confirmations.json:publish", "tags": ["硬闸门"],
         "done": lambda st: bool(st["confirmations"].get("publish"))},
        {"name": "交付教程成品 → delivered", "tags": ["自动"],
         "done": lambda st: _s(st, "delivered")},
    ],
}


def _s(st, stage):
    return bool(st.get(stage, {}).get("satisfied"))


def current_stage(st):
    """当前 stage：软回环锚点（rolled_back_to）优先，否则第一个未完成阶段。"""
    conf = st.get("confirmations", {}) or {}
    rb = conf.get("rolled_back_to")
    if rb in STAGE_TO_PHASE:
        return rb
    cur = _TRACKED[0]
    for s in _TRACKED:
        cur = s
        if not _s(st, s):
            return s
    return cur


def _render_step(step, seq, is_current):
    checkbox = "[✓]" if step["done"] else "[ ]"
    tags = " ".join(f"[{t}]" for t in step["tags"])
    marker = "  ← 当前" if is_current else ""
    return f"- {checkbox} Step {seq} {step['name']} {tags}{marker}"


def render_micro(st, stage=None):
    """微观 checklist（§3.2/§6.3）。"""
    stage = stage or current_stage(st)
    phase = STAGE_TO_PHASE.get(stage, 1)
    lines = [PHASE_NAMES[phase], "Progress:"]
    cur_seq = None
    for seq, spec in enumerate(MICRO_STEPS.get(stage, []), start=1):
        step = dict(spec)
        step["done"] = bool(spec["done"](st))   # 从状态推导完成位
        if not step["done"] and cur_seq is None:
            cur_seq = seq
        lines.append(_render_step(step, seq, seq == cur_seq))
    return "\n".join(lines)


def render_macro(st):
    """宏观仪表盘（§3.1/§6.2）：5 用户阶段 + 当前阶段展开 micro。"""
    cur = current_stage(st)
    cur_phase = STAGE_TO_PHASE.get(cur, 1)
    lines = ["📝 教程流水线进度", ""]
    for phase in range(1, 6):
        title = PHASE_NAMES[phase]
        if phase < cur_phase:
            lines.append(f"{title} [✓]")
        elif phase == cur_phase:
            lines.append(f"{title} [当前]")
            micro = render_micro(st, cur).splitlines()
            for ml in micro[1:]:          # 跳过微观层的阶段名行，避免重复
                lines.append("  " + ml)
        else:
            lines.append(f"{title} [待开始]")
    return "\n".join(lines)


def blocker_hint(reasons):
    """阻塞提示（§3.5）：阻塞原因 + '你可以：' 选项块。"""
    if not reasons:
        return ""
    joined = "；".join(reasons)
    lines = [f"⚠️ 当前阻塞：{reasons[0]}", "", "你可以："]
    if "硬闸门" in joined:
        lines.append("- 拍板确认 → 我写入 confirmations.json 继续")
        lines.append("- 回退修改 → 我重置对应闸门，旧产物保留可比")
    if ("缺 " in joined or "没有" in joined or "机检" in joined
            or "不通过" in joined):
        lines.append("- 补齐产物 → 我先补跑/修到达标再继续")
    lines.append("- 暂停 → 进度已落 progress.md，随时 resume 恢复")
    return "\n".join(lines)
