---
name: gin-qc
description: 验收单篇教程的可执行性、可验证性、覆盖完整性、证据引用、文风和 Markdown 成品。用于质检教程或检查 AI 腔；报告问题，不代写正文、不伪造执行或人工审阅结果。
---

# gin-qc：教程有效性与成品验收

完整验收读 [验收协议](references/acceptance.md)。只检查文风时运行 `qc.py check --file ... --tutorial-type 操作型`，不要启动与请求无关的发布流程。

先安装本技能的 requirements.txt。完整验收顺序：

1. 读取当前稿、v3 大纲、答案 manifest 和资料库。核对所有关键断言已登记、原文支持结论及范围；自动引用完整性不能替代此判断。
2. 在声明环境中按成功标准实际验证。只执行当前任务已授权的操作，涉及外部副作用时遵守相应授权边界。无法执行就记录 not_verified，不能以“看起来可运行”冒充通过。概念或决策教程用应用题／样例推演记录观察结果。
3. 保存结果与日志，运行：

```bash
python3 scripts/tutorial_check.py --file chapters/article-id.md --outline outlines/大纲_问题.json --manifest answers/answers-manifest.json --library library --verification verification/article-id.json --output qc/article-id.json
python3 scripts/render_markdown.py --file chapters/article-id.md --html previews/article-id.html --output qc/article-id.render.json
```

4. 打开实际 HTML，检查桌面和窄屏的代码、表格、图片、警告块及目录。生成成功不等于视觉审阅通过。通读关键路径，检查术语、隐藏步骤、失败分支和适用范围。
5. 报告四个有效性维度、风格诊断和人工审阅结果。fail 阻断，not_verified 不当作通过，not_applicable 必须解释原因。风格总分不能抵消证据或学习目标失败。

渲染方言为 CommonMark + 表格 + 删除线 + 脚注，原始 HTML 不执行，隐藏施工注释不显示。代码不参与散文风格统计；操作／排错／决策／对比原型不因缺疑问句或“你”称呼扣分，v3 不用数字密度代理证据。

本地链接与锚点默认检查；外链默认 not_checked。需要在线复核时加 --check-remote：404/410 是确定失效，权限／限流和超时分别记录，不统称坏链接。网络结果有时效，按发布要求复核。

编排器汇总各篇报告；人工确认与发布授权由编排器记录到当前产物，不由检查脚本自动授予。
