---
name: xiejiaocheng
description: 编排教程写作流水线，串联资料发现、采集、问题研究、大纲、正文与验收，处理当前产物认账、阶段恢复和授权记录。用于从主题持续推进到教程交付；单阶段请求路由到对应原子技能。
---

# 写教程编排器

编排器负责顺序、认账、确认与汇报；内容与证据由原子技能生产。先读 [生产协议](references/production-contract.md)，尤其是目录、报告与迁移要求。

主题 → source-scan/harvest → gin-question → 选题 → gin-answer → gin-outline → 大纲确认 → gin-draft → gin-qc → 人工审阅与发布确认。

- 当前会话已有授权持续有效；批内与普通批次之间自动推进并汇报，不为同一动作重复求确认。确认记录只记录用户真实决定，不替用户生成授权。
- 选题、大纲、人工审阅、发布分别留记录；必要确认只在用户尚未授权、或产物实质变化使旧确认失效时提出。已经授权的实施可继续，不能把技能文档解释为强制重复询问。
- 资产须可解析、契约有效、文章集合完整且输入／检查器哈希一致。存在一个文件不等于完成阶段。
- stage3 manifest 只包含本次选定要写的卡片；每张卡对应一篇大纲和正文。未选题留在上游问题池，不用未采用字段暗中绕过文章集合验收。
- 原子技能可独立运行；旧产物重新验证后回流。原子技能升级时同步检查协议兼容性，不能假定编排器永远无感。

每次开始、恢复和阶段变化运行 `python3 scripts/flow_controller.py resume --dir 工作目录`，展示简短进度与阻塞原因。推进前运行 next，失败就修复上游，不把手改 JSON 当作处理。

```bash
python3 scripts/flow_controller.py next --dir 工作目录 --to stage5
python3 scripts/flow_controller.py collect-qc --dir 工作目录
python3 scripts/flow_controller.py confirm --dir 工作目录 --topic "用户选定主题"
python3 scripts/flow_controller.py confirm --dir 工作目录 --gate outline
python3 scripts/flow_controller.py confirm --dir 工作目录 --gate l4 --l4-items "证据审阅结果,学习路径审阅结果,桌面审阅结果,窄屏审阅结果"
python3 scripts/flow_controller.py confirm --dir 工作目录 --gate publish
```

示例确认命令仅在相应用户决定或人工审阅实际发生后执行。collect-qc 只汇总真实报告，不自动完成 L4。confirm 将决定绑定当前产物；改稿、来源变化或检查器变化后须重新验收，相应确认也会失效。

用户要求回退时使用 rollback --to topic/stage4/stage6/delivered：保留产物用于比较，清除对应下游确认。资料／答案／正文要重做时重跑对应原子技能。

汇报显示阶段成果、关键判断、验收情况和下一步。审核时展示足以判断的目录或正文；长稿可提供可直接打开的成品，不把内部施工 JSON 当作读者交付物。

单阶段路由：挖资料 → source-scan/harvest；找问题 → gin-question；研究问题 → gin-answer；设计结构 → gin-outline；写正文 → gin-draft；质检 → gin-qc。不要为了单阶段请求启动整条发布流程。
