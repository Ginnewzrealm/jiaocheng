---
name: gin-question
description: 从真实网页和原始问题标题检索某主题的用户疑问，输出结构化问题清单、覆盖缺口与检索审计。用于发现选题或全面研究用户问题；已有明确问题时直接进入答案研究，不重复启动问题发现。
---

# gin-question：发现真实问题

问题必须来自真实检索。脚本负责抽取、去重、过滤、覆盖和停止判定；搜索与抓取由当前环境可用的工具执行。支持任意能生成输入 manifest 的 Agent，不绑定特定模型或搜索服务。

## 流程

1. 从搜索结果提取主题同义词、别称和术语，不凭空生成所谓真实问题。
2. 按基础、旅程、人群场景、争议时效四视角检索。scripts/parallel_agents.py 生成任务；检索 Agent 不再递归创建子 Agent。
3. 抓取页面原文。优先从正文抽取；无法抓取时仅接受可验证的原始疑问标题。摘要、AI 聚合回答和根据材料倒推的问题不进入候选。强反爬页面可用 scripts/fetch_url.py 的浏览器兜底。
4. 把搜索结果、抓取正文及真实轮次记录写入 manifest，运行处理脚本。
5. 根据 unresolved_cells 和 recommended_queries 补搜，更新 manifest 后重跑。只有 complete 为 true 才能宣布检索完成。

    python3 scripts/pipeline.py --manifest manifest.json --output-dir output --max-search-calls 100

输出 problem_list.json、problem_list.md、audit_report.json。退出码 0 为检索完成，1 为尚有缺口或预算耗尽（已有结果仍输出），2 为输入/工具错误。

## 判定规则

- 抽取与 QM1–QM3 过滤见 [客观规则](references/objective-rules.md)。脚本过滤后复核真实求知意图与语境，排除漏过的反问/广告。去重使用确定性文本相似度启发式，不能声称完成了模型语义判断。
- 同一问题重复出现在查询结果里不提高来源数。一手源至少 1 个、二手源至少 2 个 URL、三手源至少 3 个 URL 才标记 confirmed；单来源真实问题可填补缺失格，但保持 single_source。
- 默认检查 16 格；抽象主题加 --abstract，仅豁免 How much 与争议。补搜两轮零新增的缺失格可记为搜索穷尽，须保留真实轮次；不能把所有缺失格直接当豁免。
- 覆盖先于饱和：未解决缺口输出 needs_backfill。补搜不计入饱和统计；普通轮连续三次新增率低于 50% 才能 saturated。
- 预算默认 100 次搜索，可显式调整。达到预算输出 budget_exhausted，报告缺口。调度搜索前检查剩余预算，不把耗尽预算冒充饱和。
- 通用模板默认 domain_profile 为 general；健康主题可显式用 health。查询生成器是模板唯一来源，年份随运行日期变化。

输入、轮次字段和状态详见 [检索记录](references/retrieval-protocol.md)；输出结构见 [schema](references/output-schema.json)；模板使用见 [模板入口](references/search-templates.md)。

本技能不回答问题、不写教程、不替下游核实证据。不把来源级别等同于提问频率或事实真伪；空结果、失败与缺口必须如实报告。
