# 检索模板入口

模板由 scripts/query_generator.py 的 templates_for() 统一提供；首次任务分配与补搜共用该入口。

    python3 scripts/parallel_agents.py "配置工具" '[]' general
    python3 scripts/parallel_agents.py "减脂" '["减肥"]' health

- general：初学者、有经验的使用者、维护人员；场景使用不同环境、维护和更新等中性表达。
- health：保留健康领域的人群和场景模板。
- 四视角与 16 格定义见 scripts/coverage_matrix.py，本文件不再重复维护完整表。
- 年份取运行日期。补搜查询由 pipeline 写入 audit_report 的 recommended_queries。
- 特定领域可据真实结果扩展查询，不能声称查询模板中的问句是已发现的真实用户问题。
