# gin-question 技能测试与优化报告

## 测试执行摘要

| 项目 | 内容 |
|---|---|
| 测试主题 | 减脂 |
| 执行方式 | 手动模拟 SKILL.md 流程（因当前无可执行脚本） |
| 检索次数 | 14 次 WebSearch |
| 输出文件 | `output/problem_list.json`、`output/problem_list.md`、`output/audit_report.json` |
| 生成问题数 | 22 条 |
| 16 格覆盖 | ✅ 完整覆盖 |
| Schema 校验 | JSON 解析通过；因未安装 jsonschema，未做完整校验 |

## 输出结果

- `output/problem_list.json`：22 条问题，12 条 confirmed，10 条 single_source。
- `output/problem_list.md`：人类可读清单。
- `output/audit_report.json`：检索审计数据。

16 格覆盖情况：

| 视角 | 子维度 | 覆盖 |
|---|---|---|
| 基础 | What / Why / Who / When / Where / How / How much | 7/7 |
| 旅程 | 认知期 / 准备期 / 执行期 / 瓶颈期 / 维持期 | 5/5 |
| 人群场景 | 人群差异 / 场景差异 | 2/2 |
| 争议时效 | 争议 / 时效 | 2/2 |

## 发现的问题

### 1. 关键：当前是"文档型 skill"，无法直接执行

SKILL.md 中列出的 `scripts/pipeline.py`、`scripts/seed_expander.py` 等文件全部不存在，`scripts/` 和 `tests/` 目录为空。用户安装后只能看到流程规范，Claude Code / OpenClaw / Cursor 等工具虽然可以按 SKILL.md 手动执行，但没有自动化入口。

**影响**：
- 无法作为原子 skill 被上游编排器调用。
- 每次执行依赖 LLM 对 SKILL.md 的解析，结果不可复现。
- 无法通过单元测试保证规则一致性。

### 2. 引用路径错误

SKILL.md Step 5 写：

```
应用 `references/qm-rules.md` 中的规则。
```

实际文件名为 `references/objective-rules.md`。

### 3. WebFetch 对知乎/部分域名被拦截

测试中发现 `WebFetch` 无法访问 `www.zhihu.com`，提示企业安全策略拦截。Skill 流程假设 Agent 可以"从网页内容中抽取真实用户问题"，但在当前环境下无法落地。

**影响**：
- 真实问题只能从 WebSearch 返回的摘要/标题中推断，来源可信度下降。
- 如果搜索引擎返回的是 AI 生成的聚合摘要（如本次多次出现），容易误判为真实问题。

### 4. `site:zhihu.com` 限定词效果差

测试中多次使用 `site:zhihu.com`，但返回结果仍以微信公众号、搜狐、百度健康等为主，知乎直接链接占比低。说明搜索引擎可能忽略该限定，或知乎内容收录受限。

### 5. Agent 并行检索的配额与稳定性风险

Skill 流程要求 4 个 Agent 并行，每个 Agent 再使用多组检索词。实际运行中：
- 子 Agent 可能继续 spawn 子 Agent，导致 WebSearch 配额快速耗尽。
- 上一个会话已出现过 200/200 配额耗尽的情况。

### 6. 16 格覆盖度检查可能过严

当前规则要求 16 个格子全部 ≥1 才停止。对于抽象主题（如"一棵树"），`How much`（成本/剂量）和`争议`可能天然稀疏，强制补搜会导致低质量问题。

### 7. 输出 schema 的 `pending_validation` 字段含义不清

Schema 要求 `pending_validation` 为必需数组，但 SKILL.md 未明确说明哪些情况会进入待验证清单。测试中将所有未达频次门槛的问题直接丢弃，导致该数组为空。

### 8. 频次门槛与 single_source 的冲突

SKILL.md 的 Step 6 写：

| 级别 | 门槛 |
|---|---|
| 一手源 | ≥1 个 |
| 二手源 | ≥2 个 |
| 三手源 | ≥3 个 |

但输出 schema 中有 `status: "single_source"`，说明允许单来源入选。规则本身存在解释空间：是"任一级别满足"即 confirmed，还是单来源但高质量也入选？

## 优化建议

### 高优先级

1. **补齐可执行脚本**
   - 至少实现 `scripts/pipeline.py` 作为统一入口。
   - 拆分模块：`seed_expander.py`、`perspective_searcher.py`、`question_extractor.py`、`deduper.py`、`qm_filter.py`、`source_grader.py`、`coverage_checker.py`、`renderer.py`。
   - 提供 `tests/test_pipeline.py` 和 `tests/test_judge_questions.py`。

2. **修复 SKILL.md 中的路径错误**
   - 将 `references/qm-rules.md` 改为 `references/objective-rules.md`。

3. **增加 WebFetch 失败的降级策略**
   - 若 WebFetch 无法访问目标 URL，从 WebSearch 返回的 `title`/`snippet` 中提取问题。
   - 在 `audit_report.json` 中标记 `"source_extracted_from_search_result": true`。
   - 对无法抓取的来源，保留 URL 但降低来源可信度一级（如 tertiary → search_snippet）。

4. **控制 Agent 并行度与配额消耗**
   - 限制每个 Agent 内部不再 spawn 子 Agent。
   - 提供 `--max-search-calls` 参数，默认 30 次。
   - 优先使用主 Agent 直接搜索，减少中间层。

### 中优先级

5. **放宽 16 格覆盖度规则**
   - 将"全部 ≥1"改为"核心 12 格必须覆盖，其余 4 格允许 0，并在 audit 中标注缺失"。
   - 或者按主题类型动态调整：实体对象类主题可豁免 `How much` 和`争议`。

6. **明确 `pending_validation` 规则**
   - 将"未达频次门槛但来源为 primary/secondary"的问题放入 `pending_validation`。
   - 在 SKILL.md 中补充说明。

7. **统一 `status` 规则**
   - 明确 `confirmed` 与 `single_source` 的判定：
     - `confirmed`：满足频次门槛或来源包含 primary。
     - `single_source`：仅单一来源但问题真实且覆盖缺失格子。

### 低优先级

8. **增加来源分级白名单的域名正则**
   - 当前 `objective-rules.md` 使用示例域名，建议改为通配规则，如 `*.gov.cn`、`*.edu`。

9. **增加输出示例的完整字段**
   - `audit_report.json` 没有 schema，建议添加 `references/audit-schema.json`。

10. **为 evals.json 增加评分标准**
    - 当前只有 prompt 和 expected_output，建议增加 `min_problems`、`required_perspectives`、`max_ai_generated_ratio` 等可量化指标。

## 建议的下一步行动

1. 先修复 SKILL.md 中的路径错误和表述问题。
2. 为 4 个视角搜索增加"不再 spawn 子 Agent"的约束说明。
3. 实现最小可运行脚本 `scripts/pipeline.py`，支持 `--topic` 和 `--output-dir`。
4. 增加 2-3 个单元测试，验证 QM 规则和来源分级。
5. 重新跑一遍减脂、一棵树、新能源汽车三个 eval case。

## 附录：本次输出文件路径

- `/Users/fubo/Downloads/Gin-s-skills-work/gin-question/output/problem_list.json`
- `/Users/fubo/Downloads/Gin-s-skills-work/gin-question/output/problem_list.md`
- `/Users/fubo/Downloads/Gin-s-skills-work/gin-question/output/audit_report.json`
