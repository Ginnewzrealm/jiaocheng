---
name: gin-question
description: |
  针对任意主题，从互联网全量检索真实用户提过的真问题，输出结构化问题清单。
  当用户说"去网上搜一下XX的问题"、"XX主题用户都在问什么"、"全量找XX的真问题"、"真实用户关于XX的疑问"、"这个领域有哪些真问题"时触发。
  也适用于上游编排器需要为某个主题生成问题清单的场景。
  不适用于：直接回答某个问题、写教程/长文、纯创意发散、已有清晰问题直接执行。
---

# gin-question：全量检索真问题

针对任意主题，从互联网全量检索真实用户提过的真问题，输出结构化问题清单。

核心原则：**问题必须来自真实网络检索，不是 AI 生成。**

---

## 适用场景

- "去网上搜一下减脂相关的问题"
- "真实用户关于新能源汽车都在问什么"
- "全量找一棵树的真问题"
- "这个领域有哪些真问题"
- 上游编排器需要为某个主题生成问题清单

## 不适用场景

- 直接回答某个问题 → 走答案生成类 skill
- 写教程/长文 → 走写作类 skill
- 已有清晰问题直接执行 → 直接做
- 纯创意发散 → 走 brainstorming 类 skill

---

## 输入

```bash
gin-question --topic "主题" [--output-dir ./output] [--max-search-calls 100]
```

| 参数 | 必填 | 说明 |
|---|---|---|
| `--topic` | 是 | 任意主题字符串，任意粒度 |
| `--output-dir` | 否 | 输出目录，默认当前目录 |
| `--max-search-calls` | 否 | 安全阀，限制最大 WebSearch 调用次数，默认 100 |

## 输出

| 文件 | 说明 |
|---|---|
| `problem_list.json` | 结构化问题清单，供下游 skill 消费 |
| `problem_list.md` | 人类可读的问题清单 |
| `audit_report.json` | 检索审计报告 |

## 执行模式

本 skill 支持两种执行方式：

1. **Claude 主导模式（默认）**：Claude 按 SKILL.md 流程直接调用 WebSearch/WebFetch/OpenCLI 完成种子扩展、4 视角检索、页面抓取，再把收集结果写入 `manifest.json`，最后调用 `python3 scripts/pipeline.py --manifest manifest.json --output-dir ./output` 生成最终文件。

2. **脚本处理模式**：如果你已经手动或通过其他工具收集好了搜索结果，可直接调用 `pipeline.py` 处理 manifest 文件。manifest 格式见 `examples/manifest-example.json`。

当前 `scripts/` 下的模块主要负责确定性处理（去重、过滤、分级、渲染），**不直接调用 Claude 的 WebSearch 工具**；网络发现部分由 Claude 按 SKILL.md 执行，或需配置外部搜索 API（未来扩展）。

---

## 执行流程

### Progress

```markdown
Progress:
- [ ] Step 1 种子词扩展 `[自动]`
- [ ] Step 2 并行 4 视角 Agent 检索 `[自动]`
- [ ] Step 3 统一抽取 Agent 提取问题 `[自动]`
- [ ] Step 4 精确 + 语义去重 `[自动]`
- [ ] Step 5 QM1-QM3 过滤 `[自动]`
- [ ] Step 6 来源分级 + 频次门槛 `[自动]`
- [ ] Step 7 16 格子覆盖度检查 `[自动]`
- [ ] Step 8 信息充分性自检 + 输出 `[自动]`
```

### Step 1：种子词扩展

基于 WebSearch 搜索 `{topic} 同义词 / {topic} 别称 / {topic} 行业术语`，从搜索结果中提取 3-10 个扩展词。

**约束**：扩展词必须出现在搜索结果中，不能自由发挥。

### Step 2：并行 4 视角 Agent 检索

每个 Agent 使用固定检索词模板，基于扩展词表并行搜索。

| Agent | 视角 | 覆盖格子 |
|---|---|---|
| 基础视角 | 5W2H | What / Why / Who / When / Where / How / How much |
| 旅程视角 | 用户时间轴 | 认知期 / 准备期 / 执行期 / 瓶颈期 / 维持期 |
| 人群场景视角 | 人群/场景差异 | 人群差异 / 场景差异 |
| 争议时效视角 | 争议/时效 | 争议 / 时效 |

**Agent 失败处理**：失败 Agent 先重试 1 次，再用更宽泛检索词补搜，最多 3 次。仍失败则标记该视角"暂缺"。

**重要约束**：每个检索 Agent 必须直接调用 WebSearch/WebFetch 完成自己的工作，不得再 spawn 子 Agent，避免递归消耗搜索配额。

### Step 3：统一抽取 Agent

从所有 Agent 返回的网页内容中抽取真实用户提出的求知性问题。

**两步法**：
1. 正则初筛：匹配疑问句式
2. LLM 二筛：判断是否为真实用户的求知性问题

**来源真实性要求**：
- 问题文本必须来自真实网页：问题详情页的标题、正文中的引用、或问答列表中的真实提问。
- 不允许从搜索引擎摘要、AI 聚合回答、或内容总结中推断/改写问题。
- 抓取优先级：
  1. `scripts/fetch_url.py` 直接 HTTP 抓取页面正文
  2. 若 HTTP 失败，使用 OpenCLI browser（真实 Chrome）抓取
  3. 若以上均失败，使用该网页在搜索结果中的 **页面标题**（title）作为问题来源——页面标题对于问答类页面通常就是用户提出的原始问题
- 不可使用摘要正文（snippet）进行推断或改写。
- 无法验证真实性的来源 → 直接丢弃，不进入候选集。

**禁止来源（必须丢弃）**：
- 搜索引擎结果页中的摘要（snippet）
- AI 聚合回答中的"可能有人问""有人好奇"等倒推文本
- 任何从非原始问题文本改写、推断、总结出的问题
- `extracted_from` 不是 `content` 或 `search_title` 的候选

**强反爬域名处理**：
- 对 `zhihu.com`、`baike.baidu.com` 等强反爬域名，`scripts/fetch_url.py` 会直接使用 OpenCLI browser 抓取，跳过无意义的 HTTP 尝试。
- 每个强反爬域名 URL 预计耗时 4-17 秒，检索 Agent 应合理控制并发，避免超时。
- OpenCLI 默认超时 60 秒，百度百科等重页面可适当放宽。

**剔除**：广告、修辞反问、命令句、AI 倒推痕迹、过度抽象、严重残缺。

### Step 4：精确 + 语义去重

1. 精确去重：文本归一化后字符串相同
2. 语义去重：相似度 ≥ 0.85 视为重复
3. 子集去重：短问题是长问题的子集则合并

保留来源更多或限定更具体的问题。

### Step 5：QM1-QM3 过滤

应用 `references/objective-rules.md` 中的规则。

**QM1 真问题**：来源真实、疑问句式、可客观回答。  
**QM2 有效问题**：有真实来源、认知缺口、客观应答域、非简单常识。  
**QM3 假问题**：
- A 虚构类：AI 倒推伪问题
- B 修辞类：反问、情绪宣泄、命令
- C 无真实意图类：过度抽象、严重残缺
- D 不可证伪类：主观价值观、未来预测
- E 补充类：残缺重复、无效二元

### Step 6：来源分级 + 频次门槛

| 级别 | 门槛 | 入选规则 |
|---|---|---|
| 一手源 | ≥1 个 | 官方、学术、标准、政府 |
| 二手源 | ≥2 个 | 权威媒体、行业报告、深度原创 |
| 三手源 | ≥3 个 | 论坛、社交媒体、问答社区 |

**状态判定**：
- `confirmed`：满足上述任一门槛，或来源包含一手源。
- `single_source`：仅单一来源，但问题真实且能覆盖当前缺失的 16 格，可入选主清单。

任一满足 → 主清单；都不满足 → 待验证清单（`pending_validation`）。

### Step 7：16 格子覆盖度检查

检查 16 个格子（基础 7 + 旅程 5 + 人群场景 2 + 争议时效 2）。

**默认规则**：16 格全部 ≥1。
**放宽规则**：对于抽象主题（如自然物、概念词），允许 `How much` 和 `争议` 两个格子为 0，但必须在 `audit_report.empty_perspectives` 中标注。其余 14 格必须覆盖。

0 覆盖 → 针对缺失格子补搜（不计入新增率统计）。

### Step 8：信息充分性自检 + 输出

```
新增率 = 本轮新增问题数 / 上轮总问题数
连续 3 轮新增率 < 50% → 停止
```

取消硬时间限制。

**检索成本控制**：
- 本 skill 的核心目标是"全面"，因此优先使用饱和终止条件，不设硬性 WebSearch 调用上限。
- 为防止极端主题或异常运行导致无限消耗，可提供可选参数 `--max-search-calls` 作为安全阀，建议默认值 100（足够覆盖大多数主题的多轮补搜）。
-  Orchestrator/上游调用时应通过此参数控制预算；普通用户直接使用时不应感受到上限约束。
- 真正需要限制的是 Agent 递归 spawn，而非总搜索次数。

输出 `problem_list.json` + `problem_list.md` + `audit_report.json`。

---

## 4 视角检索词模板

### 基础视角

```yaml
What: "{扩展词} 是什么 / 定义 / 什么意思"
Why: "{扩展词} 为什么 / 原理 / 原因"
Who: "{扩展词} 适合谁 / 人群 / 谁需要"
When: "{扩展词} 什么时候 / 多久 / 最佳时机"
Where: "{扩展词} 哪里 / 场景 / 在什么地方"
How: "{扩展词} 怎么做 / 步骤 / 方法"
How much: "{扩展词} 多少 / 标准 / 剂量 / 成本"
```

### 旅程视角

```yaml
认知期: "{扩展词} 新手 入门 是什么 值得吗"
准备期: "{扩展词} 准备 需要 第一次 怎么开始"
执行期: "{扩展词} 怎么做 方法 步骤 频率"
瓶颈期: "{扩展词} 平台期 出错 受伤 怎么办 没效果"
维持期: "{扩展词} 维持 保持 不反弹 进阶"
```

### 人群场景视角

```yaml
人群差异:
  - "{人群} {扩展词} 注意"
  - "{人群} {扩展词} 禁忌"
  - "{人群} {扩展词} 区别"
  人群池: [女性, 男性, 青少年, 老人, 孕妇, 哺乳期, 糖尿病, 高血压, 甲状腺, 高血脂, 运动员, 健身爱好者, 体力劳动者]

场景差异:
  - "{扩展词} 出差 旅行 怎么办"
  - "{扩展词} 经期 生理期 怎么办"
  - "{扩展词} 怀孕 哺乳 怎么办"
  - "{扩展词} 感冒 生病 怎么办"
```

### 争议时效视角

```yaml
争议:
  - "{扩展词} 争议"
  - "{扩展词} 哪个好 对比"
  - "{扩展词} 智商税"
  - "{扩展词} 伪科学"
  - "{扩展词} 反常识"
  - "{扩展词} 骗局"

时效:
  - "{扩展词} 历史 起源"
  - "{扩展词} 演变 发展"
  - "{扩展词} 2025 最新"
  - "{扩展词} 未来 趋势"
  - "{扩展词} 新技术 新方法"
```

---

## 输出 Schema

### problem_list.json

```json
{
  "topic": "减脂",
  "generated_at": "2026-08-31T12:34:56Z",
  "exit_reason": "saturated",
  "retrieval_rounds": 3,
  "problems": [
    {
      "id": "P001",
      "text": "上班族减脂怎么吃？",
      "original": "上班族减脂期间应该怎么吃？",
      "retrieval_perspective": "人群场景",
      "sub_dimension": "场景差异",
      "sources": [
        {"url": "https://...", "type": "secondary", "frequency": 5}
      ],
      "total_frequency": 5,
      "source_count": 1,
      "duplicates": ["减脂怎么吃？"],
      "status": "confirmed"
    }
  ],
  "pending_validation": []
}
```

`pending_validation` 存放未达频次门槛、但由 primary/secondary 来源提出的问题，或单来源但高价值的问题，供人工/下游二次确认。若不存在此类问题，返回空数组。

### audit_report.json

```json
{
  "topic": "减脂",
  "generated_at": "2026-08-31T12:34:56Z",
  "search_terms_total": 24,
  "candidates_total": 156,
  "duplicates_merged": 34,
  "qm1_rejected": 0,
  "qm2_rejected": 12,
  "qm3_rejected": {"A": 0, "B": 5, "C": 8, "D": 10, "E": 5},
  "frequency_rejected": 19,
  "perspective_coverage": {
    "基础": {"What": 3, "Why": 2, "Who": 2, "When": 1, "Where": 2, "How": 4, "How much": 2},
    "旅程": {"认知期": 2, "准备期": 1, "执行期": 4, "瓶颈期": 3, "维持期": 2},
    "人群场景": {"人群差异": 4, "场景差异": 3},
    "争议时效": {"争议": 2, "时效": 1}
  },
  "agent_failures": [],
  "empty_perspectives": []
}
```

---

## 异常处理

| 场景 | 退出码 | 处理 |
|---|---|---|
| topic 为空 | 2 | 返回错误提示 |
| 全部 Agent 失败 | 1 | 返回空清单 + audit |
| 部分 Agent 失败且补搜失败 | 0 | 返回结果，audit 标记暂缺 |
| 主题无网络讨论 | 1 | 返回空清单 + audit |
| 覆盖度未全 | 0 | 针对缺失格子补搜 |

---

## 边界 / 不做事项

- 不回答问题
- 不生成教程/长文
- 不做主观判断
- 不替代下游研究 skill
- 不设置敏感词拦截（只写边界声明）
- 不做 AI 味检测（只保留输出禁区作为规则约束）
- 不做类型分布检查
- 不设置硬时间上限

---

## 参考资料

按需读取：

- `references/objective-rules.md` — 客观化规则手册（QM 规则、来源分级域名表、疑问句正则）
- `references/search-templates.md` — 4 视角检索词模板
- `references/output-schema.json` — 完整输出 schema

---

## 文件结构

```
gin-question/
├── SKILL.md
├── references/
│   ├── objective-rules.md
│   ├── search-templates.md
│   └── output-schema.json
├── scripts/                    # 可执行脚本（已实现）
│   ├── pipeline.py             # 统一入口：处理收集到的 manifest
│   ├── common.py               # 公共工具
│   ├── fetch_url.py            # HTTP → OpenCLI 兜底抓取
│   ├── seed_expander.py        # 从搜索结果提取扩展词
│   ├── parallel_agents.py      # 4 视角检索词生成
│   ├── retry_agent.py          # 重试逻辑
│   ├── question_extractor.py   # 从页面/标题提取真实问题
│   ├── dedupe_questions.py     # 精确 + 语义 + 子集去重
│   ├── judge_questions.py      # QM1-QM3 过滤
│   ├── source_grader.py        # 来源分级
│   ├── coverage_matrix.py      # 16 格覆盖度
│   ├── saturation_checker.py   # 饱和终止判断
│   └── output_renderer.py      # JSON/Markdown 输出
├── tests/                      # 单元测试（已实现）
│   ├── test_pipeline.py
│   ├── test_judge_questions.py
│   ├── test_source_grader.py
│   └── test_dedupe_questions.py
├── evals/
│   └── evals.json
├── examples/                   # 示例输入
│   └── manifest-example.json
└── output/                     # 示例输出（测试产物）
    ├── problem_list.json
    ├── problem_list.md
    ├── audit_report.json
    └── test-report.md
```

**脚本运行方式**：

```bash
# 1. 由 Claude 按 SKILL.md 流程完成种子词扩展、4 视角检索、网页抓取，生成 manifest.json
# 2. 使用 pipeline.py 处理 manifest，生成最终输出
python3 scripts/pipeline.py --manifest examples/manifest-example.json --output-dir ./output
```

**单元测试**：

```bash
python3 tests/test_judge_questions.py
python3 tests/test_source_grader.py
python3 tests/test_dedupe_questions.py
python3 tests/test_pipeline.py
```
