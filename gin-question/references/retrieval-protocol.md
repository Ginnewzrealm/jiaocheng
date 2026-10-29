# 检索记录与停止判定

输入保留 topic、expanded_terms、search_results、fetched_pages，见 ../examples/manifest-example.json。可选字段：

```json
{
  "domain_profile": "general",
  "search_calls": 12,
  "max_search_calls": 100,
  "rounds": [
    {"round": 1, "prev_total": 0, "new_count": 10, "backfill": false},
    {"round": 2, "prev_total": 10, "new_count": 0, "backfill": true, "target_cells": ["旅程/瓶颈期"]}
  ]
}
```

round 递增；prev_total/new_count 是真实去重后的问题数。普通轮进入饱和统计，补搜轮必须列 target_cells。同格连续两次补搜零新增，才可列入 empty_perspectives；普通轮发现新问题会保守重置补搜穷尽记录。记录仍需可审计，脚本不能证明外部搜索实际发生。

缺少 rounds 的旧输入仍可处理，但不能证明饱和。search_calls 缺省按 search_results 查询组数量估计；调度者须记录失败与重试在内的调用数，并在发起搜索前控制预算。pipeline 不执行外部搜索，也不会补写轮次。

| exit_reason | 含义 | complete |
|---|---|---|
| needs_backfill | 有未解决覆盖缺口 | false |
| needs_more_rounds | 覆盖可接受，但普通轮不足以证明饱和 | false |
| budget_exhausted | 达到调用预算，停止并报告缺口 | false |
| saturated | 覆盖可接受，且普通轮连续三次新增率 <50% | true |

覆盖基于主清单（包括如实标注的 single_source），不靠待验证池凑格。空结果不证明网上没有讨论。

搜索失败先重试一次，再用宽泛查询；单视角最多三次尝试，仍失败记 agent_failures。重试计入预算。正文不可触达但标题符合来源要求时可保留标题问题，不能伪造正文。
