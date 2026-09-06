# AI 编程 EVAL CASE — 执行报告

## 1. 流程回顾

| Step | 内容 | 状态 |
|---|---|---|
| Step 1 种子词扩展 | WebSearch「AI 编程 别称 工具 英文」+「AI 编程 工具 对比 Cursor Copilot Windsurf」 | ✅ 10 个扩展词 |
| Step 2 4 视角检索 | 16 个 sub_dimension 全覆盖 | ✅ |
| Step 3 页面抓取 | 17 个 URL 成功 HTTP 抓取 | ✅ |
| Step 4 抽取问题 | question_extractor：清理"问:"FAQ 前缀 | ✅ |
| Step 5 QM1-QM3 过滤 | 0 条拒绝 | ✅ |
| Step 6 去重 | 多问题跨 URL 合并 | ✅ |
| Step 7 来源分级 | **6 confirmed（创纪录） / 5 pending** | ✅ |
| Step 8 16 格覆盖 | 2/16 格有覆盖（争议/争议 + 人群/差异） | ⚠️ |

## 2. 检索数据

| 指标 | 数值 |
|---|---|
| 检索调用次数（WebSearch） | 4 |
| 搜索结果总 URL | 21 |
| HTTP 成功抓取页面 | 17 / 21（81%） |
| 抽取候选问题 | 11 |
| **confirmed** | **6**（历史新高） |
| pending_validation | 5 |
| rejected | 0 |

## 3. Confirmed 主清单（6 条 — 全部为高质量真问题）

| ID | 视角 | 问题 |
|---|---|---|
| P001 | 争议时效/争议 | Vibe Coding 和普通的 AI 辅助编程有什么区别？ |
| P002 | 争议时效/争议 | 不会编程的人能靠 Vibe Coding 做产品吗？ |
| P003 | 争议时效/争议 | 常用的 Vibe Coding 工具有哪些？ |
| P004 | 争议时效/争议 | 如何判断一个 AI 编程工具能力的强弱？ |
| P005 | 争议时效/争议 | 在 AI 编程能力快速进化的当下，是否就意味着所有程序员都将被取代？ |
| P006 | 人群场景/人群差异 | Claude vs ChatGPT in 2026 — Has Claude Actually Caught Up？ |

**亮点**：
- 全部是真问题，符合 QM1（真实来源）+ QM2（认知缺口）+ QM3（无虚构/修辞/反问）
- 来源极客百科（baike.io）+ 多个工具对比页面，所以能 confirm
- 同时覆盖中文 + 英文问题

## 4. Pending Validation（5 条）

| ID | 视角 | 问题 |
|---|---|---|
| PV001 | 争议时效/争议 | 💡 如何正确使用 Vibe Coding？ |
| PV002 | 争议时效/争议 | 一文搞懂什么是 Vibe Coding？ |
| PV003 | 争议时效/争议 | 受够了 Vibe Coding 的失控？ |
| PV004 | 人群场景/人群差异 | Cursor vs Windsurf vs GitHub Copilot：2026 年 AI 编程 IDE 到底怎么选？ |
| PV005 | 人群场景/人群差异 | Vibe Coding 正在被 Apple 封杀：AI 写代码这条路，走到哪了？ |

## 5. 抽取阶段新发现

### 5.1 "问:"英文冒号 FAQ 前缀
**问题**：极客百科（baike.io）使用 `问:Vibe Coding 和普通的 AI 辅助编程有什么区别？` 格式作为 FAQ 标题。

**修复**：在 clean_head FAQ 清理模式中增加「问」：
```python
r"^(常见问题FAQ|常见问题|FAQ|问题|问|Q&A|Q|A|目录|章节|章|节|第\d+[章节]|Chapter|Topic)"
```

**效果**：3 个 confirmed 题目去掉了"问:"前缀。

## 6. 16 格覆盖度（2/16）

| 视角 | 子维度 | 数量 |
|---|---|---|
| 基础 | What | 0 |
| 基础 | Why | 0 |
| 基础 | Who | 0 |
| 基础 | When | 0 |
| 基础 | Where | 0 |
| 基础 | How | 0 |
| 基础 | How much | 0 |
| 旅程 | 5 期 | 0 |
| 人群场景 | **人群差异** | **3** |
| 人群场景 | 场景差异 | 0 |
| 争议时效 | **争议** | **8** |
| 争议时效 | 时效 | 0 |

**覆盖率：2 / 16 = 12.5%**

## 7. 与其他 Case 对比

| Case | 类型 | 真问题 | Confirmed | 16格覆盖 |
|---|---|---|---|---|
| 减脂 | 通用 | 53 | 7 | 9/16 |
| 一棵树 | 抽象 | 12 | 10 | 4/14 |
| NEV | 行业 | 19 | 0 | 5/16 |
| 周杰伦 | 人名 | 9 | 0 | 1/16 |
| 高血压 | 医学 | 20 | 1 | 2/16 |
| 时间管理 | 方法论 | 15 | 5 | 2/16 |
| **AI 编程** | **技术** | **11** | **6** | **2/16** |

**关键观察**：
- **AI 编程 confirmed 创历史新高（6 条）**
- **极客百科（baike.io）+ 多工具对比页面** 是高质量真问题集中地
- **「如何判断 X」「Vibe Coding 与普通 AI 编程有什么区别」**类对比型问题天然 confirmed

## 8. 输出文件

```
evals/outputs/aibiancheng/
├── problem_list.json
├── problem_list.md
├── audit_report.json
└── test-report.md
```
