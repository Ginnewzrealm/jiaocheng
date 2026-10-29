---
name: gin-tutorial-harvest
description: 将来源清单采集为本地 Markdown 资料库，记录成功、失败、通道与覆盖关系，生成可复核的 coverage-manifest.json。用于批量采集和教程资料准备；发现来源走 source-scan，单条收藏走 collector。
---

# gin-tutorial-harvest：采集与验收

输入 topic、sources.json、output_dir。每次采集更新 harvest-records.json；汇总只认已登记、内容未变化的成品，失败、待采和冗余记录仍保留。

## 最短流程

1. source-scan 提供 sources.json。只有 URL 清单时先补 title、layer、action 等字段。整条来源对象可保存为 source.json 传给命令，避免重复录入 URL、定级与覆盖关系。
2. 用 harvest-one 调度。普通网页自动采集；浏览器/collector 通道返回明确交接信息，Agent 执行后用 register 登记成品。
3. 失败先看返回的分类和建议，再决定重试或换通道，策略见 [采集边界](references/collection-policy.md)。
4. 核对每份成功资料实际覆盖哪些问题，在 sources.json 的 covers 中记录；整站返回的新页面必须逐页核对，不继承根页面的覆盖结论。
5. manifest 汇总，报告覆盖缺口、资料不足、失败源和观察哨。补采后重新汇总，不手改报告。

    python3 scripts/harvest.py harvest-one --dir library --source-json source.json
    python3 scripts/harvest.py register --dir library --file L3/article.md --source-json source.json --channel opencli
    python3 scripts/harvest.py manifest --dir library --topic "主题" --sources sources.json

仍支持 harvest-one 的 --url/--title/--layer/--value/--action 逐条参数。register 的 --file 为资料库内相对路径或绝对路径。

## 来源与覆盖

sources.json 示例：

    {
      "topic": "配置工具",
      "questions": ["如何配置工具？"],
      "sources": [{
        "url": "https://example.org/guide",
        "title": "配置说明",
        "layer": "L1",
        "value": "high",
        "action": "单页采集",
        "covers": ["如何配置工具？"],
        "original_source_id": "publisher:guide"
      }]
    }

covers 记录实际内容映射，不以重复关键词凑覆盖。original_source_id 按真实出处填写，不能为提高来源数编造独立身份。冗余源标 redundant_with，替补标 替补自；完整对象会保留这些字段。

- 默认 full：总内容单位至少为目标成稿三倍（--target-words 默认 8000），每题至少两组来源。
- 明确单问题可显式 --mode focused：不设三倍字数配额，每题至少一组来源，必须有有效成品。与 source-scan 使用相同模式；答案证据、实际验证和人工审阅要求不变。
- 单篇默认至少 500 内容单位。短小官方说明可显式 --min-chars 调整并在来源 note 说明原因，仍需验收正文真实性。
- 中文字数 + 英文词数计量，权威材料不限语言。同域/同原始出处保守合并；空问题清单不通过。
- unknown 源照常采集并列入观察哨，目录层级和保存成功不证明权威。

## 通道与依赖

- 普通页面：npx -y firecrawl-cli scrape，保留 --only-main-content。
- 整站扒取：有 key 时使用支持的 crawl --wait 命令逐页落盘，--limit 默认 30；保留原通道名 firecrawl-download。达到范围上限不意味着穷尽整个站点。未完成或仍有分页时不报告完成。
- 无 key 的整站请求降级为单页 scrape，返回实际通道；需要多页时补 key 或逐条采集，不能把单页称为整站完成。
- 知乎/登录墙/B站专栏：可用浏览器通道；PDF/公众号/视频：collector；书籍链接只记录书目。
- key 从 ~/.config/gin-tutorial/config.yaml 读取并注入子进程，不要求手动 export。配 key 后仍受服务套餐/配额约束。
- 浏览器或 collector 不可用时如实报告该通道未采，不替换成伪造正文。

本技能独立目录包含 harvest_store.py 和 source_coverage.py。旧资料须用 register 补全真实 URL、通道和覆盖映射；不再通过扫描所有 Markdown 把临时文件、错误页或未知来源认作成功。

退出码：0 操作成功/验收通过，1 采集或质量未通过，2 输入或工具异常。验收失败仍保留记录供补采。
