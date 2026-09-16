---
name: gin-outline
description: 将一张达标答案卡组织成单篇教程大纲，选择教程原型并声明读者、前置条件、环境、成功标准与证据引用。用于设计教程结构；不负责补采证据、写正文或替用户决定选题。
---

# gin-outline：按读者任务组织教程

输入已选定问题的 v3 answers-manifest.json 与资料库，输出人读目录表和机读施工单。一题一文；用户明确要求综述时再扩大范围。

1. 读取 [原型选择](references/tutorial-archetypes.md)，按读者任务选择 tutorial_type。保留答案卡的“类型”，它描述研究任务，两者不可互相覆盖。
2. 按 [输出模板](references/output-templates.md) 填读者、目标、前置条件、范围、环境、成功标准、失败边界与交付物。技术主题写版本和平台；其他主题用适用人群与证据时间等条件。未知环境如实记录，不能伪称完成复现。
3. 每节一个学习台阶，记录稳定 section_id、施工说明和真实 claim_id。操作步骤具备动作、预期结果、验证方法及失败处理；概念型用练习检验理解。节数服从任务，不为满足 5–8 节灌水。
4. .md 只放可读目录与目标；.json 保存证据、路径和步骤，结构一致。原有叙事建议见 [大纲方法论](references/outline-methodology.md)，仅在适合原型时采用。
5. 执行检查，错误修复后再交付大纲：

```bash
python3 scripts/outline.py check --outline outlines/大纲_问题.json --manifest answers/answers-manifest.json --library library --output checks/article-id.outline.json
```

脚本核对卡片达标、原文证据、引用 ID 与教程契约；未知证据 ID 不放行。报告绑定大纲、manifest、来源和检查器。旧大纲可单项检查，但须补齐 v3 契约才能参与流水线认账。

缺口用 gaps 子命令单独输出；缺证据回 gin-answer，不在大纲编造。审核时展示目录和关键成功标准；已有授权按当前会话执行，不重复索取相同确认。
