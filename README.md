# jiaocheng：教程写作技能组

从真实问题和资料出发，产出有证据、成功标准、失败处理与成品验收的教程。

## 流水线

`source-scan → harvest → gin-question → gin-answer → gin-outline → gin-draft → gin-qc`

xiejiaocheng 负责路由、当前产物认账、阶段恢复与确认记录。七个原子技能仍可单独使用。

| 层 | 产物与职责 |
|---|---|
| 资料与问题 | 六层资料地图、采集库、覆盖记录、真实问题清单 |
| 答案 | 原始出处、快照、原文摘录、适用范围、结论 ID、支持关系核验 |
| 大纲 | 教程原型、读者、前置条件、环境、成功标准、失败边界、交付物 |
| 正文 | 按小节使用结论脚注，操作步骤带预期结果、验证方法与失败处理 |
| 验收 | 四个教程有效性维度、实际结果日志、文风、Markdown 解析与 HTML 预览 |
| 编排 | 按完整文章集合认账，检查报告和确认绑定当前文件及检查器 |

## v3 生产协议

- 研究类型（事实／方法／争议）与教程原型（操作／概念／排错／对比／决策／实战）分开。
- errors、warnings 始终是数组；status 为 pass/minor/fail。退出码 0 通过或 minor，1 质量失败，2 输入或工具错误。
- 来源落盘不等于权威，同域或同源材料不重复提高置信度；validate 只读，manifest 输出重新验证和复算后的 cards。
- 关键结论 ID 必须真实存在，引用贯通到对应小节正文；字符串“研究表明”不再承担证据验收。
- 来源、正文、大纲、核验日志、预览或检查器变化后，旧报告失效。旧格式须补齐真实信息并重新验收，不自动补写 verified。
- 原始 JSON、核验记录、报告都是可审计记录，不能自行证明作者说的事实正确；关键证据支持和实际成品仍需审阅。

详细格式与命令见 [生产协议](xiejiaocheng/references/production-contract.md)、[证据协议](gin-answer/references/evidence-standard.md)、[大纲模板](gin-outline/references/output-templates.md)、[验收协议](gin-qc/references/acceptance.md)。

## 安装与运行

脚本支持 Python 3.9 及以上。资料、答案、大纲与编排脚本使用标准库；完整成品验收需安装 Markdown 解析依赖：

```bash
python3 -m pip install -r gin-qc/requirements.txt
python3 xiejiaocheng/scripts/flow_controller.py status --dir 教程工作目录
```

各技能 scripts 内包含自足的 tutorial_contract.py。维护者编辑 shared/tutorial_contract.py 后运行 `python3 scripts/sync_contracts.py`；CI 用 --check 防止副本漂移。单独安装技能时复制其整个目录即可，不依赖相邻技能才能导入协议。协同工作仍按各技能声明传入上游产物。

## 验证

```bash
python3 -m pip install pytest
python3 scripts/sync_contracts.py --check
python3 -m pytest -q
```

新增 tests/test_pipeline_contracts.py 用真实生产者输出驱动下游，覆盖正常闭环、错误退出码、虚构引用、旧哈希、缺失验证、缺篇和 Markdown 结构。测试样例是明确标注的合成夹具，不当作真实读者学习效果基线。

原有 gin-draft/gin-qc 的真实章节样本尚未随库提交，18 个相关测试会 skip；补入合法可分发的 fixtures 后恢复。这不是已完成真人学习验证的声明。样本治理与评估记录见 [corpus](corpus/README.md)。
