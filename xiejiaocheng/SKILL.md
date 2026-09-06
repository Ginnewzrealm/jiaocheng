---
name: xiejiaocheng
description: 教程写作流水线编排器。给一个主题，把 source-scan/harvest/gin-question/gin-answer/gin-outline/gin-draft/gin-qc 七个原子技能串成完整生产线，带资产认账（单独跑过的阶段自动跳过）、4 个硬闸门（人必须拍板才能推进）和分批汇报。当用户说"用流水线跑一个 XX 教程"、"把 XX 主题从选题做到发布"或要求连续执行多个阶段时使用。
---

# xiejiaocheng 写教程编排器

七原子技能的路由器。原子技能各管一段，本技能管**顺序、认账、闸门、汇报**。

## 铁律

1. **只调不改**——永远不改原子技能的代码和产物格式。原子技能升级，编排器无感。
2. **资产认账**——每个阶段开工前先扫描其上游产物，存在且有效就标 `satisfied` 直接跳过。用户单独触发过任何原子技能（比如只跑了 gin-question），产物放进 tutorial 目录（可用软链），流水线自动接住，不重跑。
3. **4 个硬闸门**——闸门不过，`validate_next` 直接拦截，不许绕：
   | 闸门 | 时机 | 记录 |
   |---|---|---|
   | 选题拍板 | 进 Stage 3 前 | `confirmations.json` 的 `topic` 字段 |
   | 大纲确认 | 进 Stage 5 前 | `outline: true` |
   | L4 人审 | 交付前 | `l4: [...]` 四项逐项签字 |
   | 发布 | 交付前 | `publish: true` |
4. **子任务循环：批内自动，批边界需确认**。一个批次内（如 gin-answer 按类型分批的批内多题）连续执行不打扰；每跨一个批边界，停下汇报，等用户确认再进下一批。
5. **blocked 即停**——任一阶段产不出合格产物，写 `blocked.md`（卡在哪、试过什么、建议怎么办），停线汇报，不许带病推进。

## 流水线

```
主题 → stage0 扒资料(source-scan+harvest) → stage1 找问题(gin-question)
     → topic 选题拍板【闸门1】→ stage3 找答案(gin-answer)
     → stage4 大纲(gin-outline) → 大纲确认【闸门2】→ stage5 写作(gin-draft)
     → stage6 质检(gin-qc) → L4人审【闸门3】+ 发布【闸门4】→ delivered
```

## tutorial 工作目录约定

```
<dir>/library/coverage-manifest.json   Stage 0 产物（资料库，可软链）
<dir>/problem_list.json                Stage 1 产物
<dir>/answers/answers-manifest.json    Stage 3 产物
<dir>/outline.json                     Stage 4 产物
<dir>/chapters/*.md                    Stage 5 章文件（非空才算）
<dir>/checks/<章名>.draft.json         Stage 5 机检报告（errors 必须 = 0）
<dir>/qc/report.json                   Stage 6 质检报告（verdict 通过/minor 才许交付）
<dir>/confirmations.json               4 闸门确认记录
<dir>/blocked.md                       卡线记录（出现时停线）
<dir>/progress.md                      阶段日志（每阶段记一行时间+产物+异常）
```

## 执行协议

每个阶段固定五拍：

1. **认账**——`python3 scripts/flow_controller.py status --dir <dir>`；该阶段 `satisfied` 就向用户报"已认账跳过"，进下一阶段。
2. **放行校验**——`python3 scripts/flow_controller.py next --dir <dir> --to <阶段>`；`can_proceed: false` 就把 `reasons` 原样报给用户（闸门类等人拍板，资产类先补跑上游）。
3. **执行**——调用对应原子技能，严格按该技能的 SKILL.md 走。
4. **验收**——原子技能自己的机检全绿才准计入产物；机检不过的修到达标，改不动就 blocked。
5. **汇报**——按下面的批次规则。

### 分批汇报（进度条协议）

- **批内【自动】**：同一批次内的子任务连续跑完再汇报。如 gin-answer 按类型分批（事实→方法→争议），批内多题连做。
- **批边界【需确认】**：每完成一批，汇报格式：
  - 这批做了什么、产物在哪
  - 机检/置信摘要（如 gin-answer：`5题：3高置信/1中/1观察哨+原因`）
  - 下一批做什么、预计量级
  - 等用户"继续"再进下一批。
- **闸门批**：到 4 硬闸门任一个，必须拿到用户明确拍板，写进 `confirmations.json` 才算数。

### 闸门记录格式

```json
{"topic": "减重和减脂的区别", "outline": true,
 "l4": ["温度感✓", "独特性✓", "姿态✓", "心流✓"], "publish": true}
```

## 单技能路由（不启动全流水线时）

用户只想跑一段时，直接路由到原子技能，产物照样认账回流：

- "挖 XX 主题的权威资料/教程" → source-scan + harvest
- "挖 XX 领域内所有问题" → gin-question
- "挖 XX 问题所有的答案" → gin-answer
- "给这些问题排个大纲" → gin-outline
- "把第 X 章写出来" → gin-draft
- "体检这章" → gin-qc

## 反模式（机检已堵，人检兜底）

- touch 空文件冒充产物（manifest 坏 JSON、空章、无 errors=0 报告的章）——flow_controller 已拒
- 没选题就开工、没确认大纲就写正文、质检不通过就交付——闸门已拒
- 一个阶段失败了跳过它先做后面——状态机顺序不可跳跃
