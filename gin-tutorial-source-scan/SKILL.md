---
name: gin-tutorial-source-scan
description: |
  针对一个教程主题（如「减脂」「Claude Code」），系统性发现网上优质教材来源，输出结构化 sources.json 清单。
  当用户说"帮我找XX主题的教材/资料/教程来源"、"XX有哪些好的学习资料"、"扒一下XX的资料"、"搜集XX教程"时触发。
  也适用于上游编排器（写教程技能组）的 Stage 0 发现层。
  不适用于：采集已圈定的具体 URL（走 gin-tutorial-harvest）、单条网页保存（走 collector）、找用户真问题（走 gin-question）。
---

# gin-tutorial-source-scan：教程资料源发现层

输入一个主题词 → 输出 sources.json（资料源清单 + 拒绝记录 + 覆盖度检查）。
核心原则：**每条来源必须经脚本定级并落盘——收录要记录，拒绝也要记录，判断可追溯。**

## 何时使用 / 不适用

- 用户只给主题词，要"全面的优质教材地图" → 本技能
- 用户已圈定 URL 清单要下载 → gin-tutorial-harvest
- 单条链接保存 → collector；登录墙内容 → opencli 通道

## 工作流程

```
1. 初始化清单   建 sources.json（schema 见下）；跑 channel 确定搜索通道
2. 六层枚举     按六层资料地图逐层搜索；每层结束：有收录，或显式声明跳过（skipped_layers，不许静默跳过）
3. 逐条定级     每条搜索结果跑 grade 定级；add 收录或 reject 记录（拒绝理由必填）
4. 收敛判定     「轮」= 单层内的收敛轮次，每层 ≤3 轮。一轮搜完：前 10 条中 ≥3 条已收录 = 该层饱和，立即停。**饱和后唯一允许继续搜的情况：coverage gap 触发的定向补搜（不计入层轮次）**
5. 覆盖检查     对 TOP 高频问题跑 coverage；gap 非"无" → 针对性补搜一轮后复检；仍不足则如实报 gap 请用户裁决（不许硬凑）
6. 硬闸门输出   向用户展示 sources.json 摘要（入选/拒绝/覆盖/gap），用户圈定后才交 harvest
```

## 搜索通道（先跑 channel）

```bash
python3 scripts/source_scan.py channel
```

- `tavily`：已配置 key（`init-config --tavily-key <KEY>`，存 ~/.config/gin-tutorial/）→ 用 tavily 搜索
- `agent-websearch`：无 key → 由 Agent 用 WebSearch 工具执行搜索，脚本照常定级落盘

## 六层资料地图（每层至少尝试一轮）

| 层 | 内容 | 查询策略 |
|---|---|---|
| L1 官方源 | 官网/政府/国际组织指南 | 主题+「指南/规范/标准 site:gov」；who.int/cdc 等 |
| L2 GitHub | awesome 清单仓库 | 「awesome <主题>」，清单仓库是金矿 |
| L3 中文社区 | 知乎高赞/公众号/掘金/少数派 | 多查询换角度：入门/误区/原理/对比 |
| L4 英文社区 | Medium/dev.to/freeCodeCamp | Google `site:medium.com <主题>` 排除官方域名 |
| L5 讨论区 | Reddit/HN/V2EX/LinuxDo 高赞帖 | 「<主题> reddit」「<主题> site:linux.do」 |
| L6 学术 | arXiv/Semantic Scholar/综述 | 「<主题> review/meta-analysis」 |

## 质量定级（必须逐条跑脚本，禁止凭印象）

```bash
python3 scripts/source_scan.py grade --title "..." --url "..." [--snippet "..."]
python3 scripts/source_scan.py add --file sources.json --title "..." --url "..." \
    --layer L3 --lang zh --value high --note "一句话价值说明" --action "单页采集"
# 冗余源（与已收录源同内容的镜像/短讯）：加 --redundant-with <已收录源 URL>
# harvest 层见标记直接跳过，不进采集队列、不烧配额
python3 scripts/source_scan.py reject --file sources.json --title "..." --reason "拒绝原因"
```

| value | 含义 |
|---|---|
| high | 官方/学术/权威医疗源、结构化文档站（docs.*） |
| medium | 认证机构/医学科普媒体、实操 PDF、经验博客 |
| unknown | 无明确信号（如知乎 UGC）→ 须读内容后人工改判 |
| reject | 营销/电商/内容农场 → **必须 reject 落盘，不许默默丢弃** |

## 特殊来源的 action 标注

| 来源类型 | action |
|---|---|
| 普通网页 | 单页采集（firecrawl scrape 免 key 即可） |
| 结构化文档站（docs.*） | 整站扒取（firecrawl download，需 key） |
| 公众号文章/PDF/视频页 | collector 采集 |
| 知乎/登录墙/强反爬 | opencli 真实浏览器通道 |
| 书籍（豆瓣/当当链接） | 找电子版/购书——**不是采集对象**，note 里写清书目 |

## 收敛与验收

- 收敛信号：一轮前 10 条中 ≥3 条已收录 → 该层池子饱和（脚本 `is_saturated` 逻辑）
- **效率规则**：同一 URL 跨查询重复出现时，复用首次 grade 定级直接 add/reject，不重复跑脚本
- **覆盖红线**：禁止为凑覆盖而修改已落盘条目的 note/title 使关键词命中——覆盖不足就补搜，补不到就如实报 gap。**改动 note 只允许一种情况：补写真实内容描述（grade 时信息不足），不许以命中关键词为目的**
- 语言政策：**教材级源（官方/学术/经典书籍）不限语言；媒体/UGC 按目标读者语言**——同一标准执行到底，不要英文官方就收、英文媒体就拒
- TOP 高频问题清单**优先来自 gin-question 输出**（其格式为关键词短语如「减脂原理」「平台期」，子串匹配依赖此格式——自拟时也必须用 ≤8 字关键词短语，**禁止用自然长句**，长句会恒匹配 0 造成假 gap）；gin-question 不可用（未安装/非编排场景）时允许自拟 8-12 个问题，但必须在 coverage_check 里显式标注 `"问题来源": "自拟"`，不许静默替代
- 覆盖标准：TOP 高频问题每个 ≥2 份独立来源；gap 必须显式列出
- 素材总量 ≥ 目标成稿 3 倍字数是 **harvest 层**的验收，本层只管覆盖度

## sources.json schema

```json
{
  "topic": "减脂",
  "generated_at": "2026-09-03",
  "rounds": 5,
  "sources": [
    {"title": "...", "url": "...", "layer": "L1", "type": "政府指南",
     "lang": "zh", "value": "high", "note": "权威背书用", "action": "单页采集"}
  ],
  "rejected": [{"title": "...", "reason": "微商产品营销文"}],
  "skipped_layers": [{"layer": "L6", "reason": "健身主题无相关学术综述可引"}],
  "coverage_check": {"高频问题": ["..."], "已覆盖来源数": {"...": 2}, "gap": "无"}
}
```

## 常见错误（实测基线观察）

| 错误 | 纠正 |
|---|---|
| 凭自己判断好坏，不落盘 | 每条必须 grade + add/reject，用户要能看到拒绝理由 |
| 跳过六层地图，搜到 10 条就停 | 每层显式覆盖或显式声明跳过；收敛由饱和信号判定，不是凑够数 |
| B站视频、书籍链接当普通网页 | 特殊来源标对 action，书不是采集对象 |
| 语言标准摇摆（英文官方收、英文媒体拒） | 教材级不限语言，媒体按读者语言，一条标准到底 |
| 静默丢弃拒收来源 | reject 必须落盘——审计链：拒绝也是判断，要可追溯 |
