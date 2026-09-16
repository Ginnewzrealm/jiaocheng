# v3 结论证据协议

保留“问题／类型／一句话答案／置信度／状态”，增加 schema_version 和 claims。以下只是结构示例，示例值不能当作已核验记录。

```json
{
  "schema_version": 3,
  "问题": "如何确认配置只对当前用户生效？",
  "类型": "方法型",
  "类型判定依据": "存在操作流程及适用条件",
  "一句话答案": "检查配置作用域和另一用户的结果。",
  "置信度": "中",
  "状态": "待补采",
  "争议点": [],
  "适用边界": ["工具版本和部署模式须另行确认"],
  "出处": [{
    "source_id": "S-001",
    "来源": "L1/config.md",
    "url": "https://example.org/config",
    "original_source_id": "vendor:config:v2.3",
    "定级": "high",
    "sha256": "填写实际文件的SHA256"
  }],
  "claims": [{
    "claim_id": "C-001",
    "statement": "这项配置的作用域是当前用户。",
    "claim_type": "限制条件",
    "scope": "工具2.3、单用户配置文件",
    "evidence": [{"source_id": "S-001", "locator": "User scope小节", "quote": "填写实际原文短摘录"}],
    "conflicts": [],
    "verification": {"support": {"status": "not_verified"}}
  }]
}
```

只有实际阅读并核对原文支持关系后，才可写：

```json
{"status": "verified", "by": "实际检查者", "at": "实际检查时间", "method": "描述如何核对原文及适用范围"}
```

- source_id 标识资料库中的一份快照；original_source_id 标识独立原始证据。同一报告的转载、镜像共享后者；DOI/版本可作为原始标识。不得为了提高置信度另编 ID。
- claim_id 在一张卡内唯一、稳定。源与结论 ID 使用字母、数字、连字符或下划线。
- 来源必须是库内真实文件，sha256 与文件字节一致；quote 必须出现在快照中。摘录存在只证明可查，不证明推断有效。
- scope 保留版本、平台、人群、时点等成立条件。conflicts 是尚未解决的冲突数组；有冲突的结论不能当成已核验达标结论使用。
- 原文支持和操作执行分开验证。读文档不能置操作已通过；成稿操作日志绑定正文、大纲和环境。
- 数据百分比需要分母和口径；版本号、端口和步骤序号不需要样本量。推断注明依据和边界。

旧卡补齐真实证据后重新 validate/manifest。不能根据旧置信度批量填 verified。旧卡仍可单项检查已有字段；流水线 manifest 要求 v3。
