# v3 生产目录与迁移

```text
library/coverage-manifest.json
problem_list.json
answers/问题.json                    v3 原始卡
answers/问题.check.json              只读检查报告
answers/answers-manifest.json        标准化 cards，仅含本次选定文章
outlines/大纲_问题.json               v3 单篇契约
outlines/大纲_问题.md                 用户审核目录
chapters/article-id.md
checks/article-id.outline.json
checks/article-id.draft.json
verification/article-id.json         成功标准的真实核验记录
verification/运行日志.txt
qc/article-id.json                   四维有效性与风格报告
qc/article-id.render.json            当前成品机械检查
qc/report.json                      collect-qc 汇总生成
previews/article-id.html
confirmations.json
progress.md
```

原子技能的命令以各 SKILL.md 为准。基本顺序为答案 validate/manifest → 大纲 check → 大纲确认 → draft check → tutorial_check 与 render_markdown → collect-qc → L4 与发布确认。

报告 schema_version=3，errors/warnings 是数组、error_count/warning_count 是对应数量，status 是 pass/minor/fail。checker 保存名称、协议版本与当前脚本文件哈希；inputs 保存绝对路径与 SHA256。不能用 error_count 代替检查 errors，也不能用中文 verdict 文案代替机器状态。

在本机重新验证可重建绝对路径记录；搬移工程后旧记录无法证明当前文件，重新运行检查。不要通过批量替换路径或哈希“迁移”验证。

认账条件：

- 资料验收 material_ok 为 true 且 coverage_gaps 为空；问题清单须是有内容的结构化清单。
- manifest 检查通过、来源与原始卡没有变化，所有 cards 达标且非低置信。
- 所有选定答案各有且仅有一篇 v3 大纲，逐篇大纲报告有效。
- 正文文件集合与 article_id 集合完全一致，各篇 draft 报告有效。
- 每篇有效性检查和渲染报告有效、关键维度通过；没有 not_verified 的成功标准。
- collect-qc 的文章集合与当前大纲一致；人工审阅／发布记录匹配当前产物。

confirm 不是事实核验或授权获取工具，只记录已经发生的决定。L4 至少记录证据、学习路径、桌面、窄屏四项实际结果。更改选题清除下游确认；更改产物使对应绑定失效，检查和用户决定须基于新版本。

## 历史产物

旧答案卡与 v2 大纲的单项检查接口保留，便于发现可复用内容。新版编排器不会把以下件认作完成：errors: 0 的手写旧报告、无哈希报告、只有中文 verdict 的报告、仅非空的大纲 JSON。

迁移顺序：备份已有产物 → 填写真实来源与 claim → 重新生成 manifest → 补齐 v3 教程契约 → 将旧稿对应到 claim 脚注和步骤 → 执行必要验证 → 重跑各报告 → 对当前稿记录实际确认。迁移不自动发明版本、摘录、日志、verified 或用户批准。

## 规则归属

证据规范归 gin-answer，原型与施工单归 gin-outline，正文呈现归 gin-draft，语义／结构／成品验收归 gin-qc，阶段集合与确认有效性归 xiejiaocheng。共享可机械验证的协议位于 shared/tutorial_contract.py，由同步工具分发到独立技能目录；修改协议后同步并跑跨阶段集成测试。
