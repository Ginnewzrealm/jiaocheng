# jiaocheng：教程写作技能组

输入一个主题词 → 网上系统性发现真实用户问题 → 找到优质教程源 → 采集为本地 Markdown 资料库 → 逐问题深度研究出答案卡 → 按学习路径重组为教程大纲 → 逐章施工写出正文 → 四层活人感终检。
写教程工作流的全流水线：素材层 + 答案层 + 结构层 + 写作层 + 质检层。**发现什么采什么全留痕，判断可追溯。**

## 编排器：xiejiaocheng

**xiejiaocheng** 是流水线路由器：给一个主题，把下面七个原子技能串成完整生产线。三个职责——**资产认账**（单独跑过的阶段检测到产物自动跳过，成果回流流水线）、**4 个硬闸门**（选题拍板/大纲确认/L4人审/发布，没确认不许推进，`scripts/flow_controller.py` 强制）、**分批汇报**（批内自动，批边界需确认）。原子技能也都能单独触发（"挖 XX 的资料"/"挖 XX 领域的问题"/"挖 XX 问题的答案"），只调不改。

## 七个原子技能

| 技能 | 角色 | 输入 → 输出 | 测试 |
|---|---|---|---|
| **gin-question** | 找问题（Stage 1） | 主题词 → 结构化真实用户问题清单 | 43 |
| **gin-tutorial-source-scan** | 发现层（Stage 0） | 主题词 → `sources.json`（六层资料地图逐层枚举，逐条质量定级，拒绝也落盘带理由，coverage 覆盖检查） | 20 |
| **gin-tutorial-harvest** | 采集层（Stage 0） | `sources.json` + 输出目录 → 按层分目录的 Markdown 资料库 + `coverage-manifest.json`（验收：素材 ≥ 3× 目标成稿字数、每 TOP 问题 ≥2 独立来源） | 35 |
| **gin-answer** | 找答案（Stage 3） | 单个问题 + 可选资料库 → 研究报告 `.md` + 答案卡 `.json`（横纵分析法改造：纵轴=由来/演变，横轴=阵营/争议，交汇=综合判断+适用边界；validate 机检出处存在性/URL/独立性，置信度自动复算防虚报） | 25 |
| **gin-outline** | 大纲层（Stage 4） | 主题（用户拍板）+ answers-manifest + 资料库 → 大纲 `.md` + `.json`（章节→卡片+素材映射）+ 缺口清单（外置）；机检 8 条：幽灵引用/映射注水/动作动词/知识章拓扑/贯穿案例钉死/synthesis gap | 20 |
| **gin-draft** | 写作层（Stage 5） | 大纲.json 一章（卡片+素材映射）+ 资料库 → 一章 Markdown 正文（章构件，装配无关）；机检：素材锚定率≥60%（堵凭空发挥+贴名凑数）、章首契约（写给谁+读完能做什么）、章末交付物（清单/表/模板）、贯穿案例出场、句式密度、卡兹克禁区词表、回环呼应（章末回扣章首）、用人话写（空洞概括拦截） | 22 |
| **gin-qc** | 质检层（Stage 6） | 一章 Markdown 正文 → 活人感质检报告（score+verdict+L4 人审项）；四层体系教程化：段落≤300字(硬规则)/中位数句长集中度/疑问句/证据密度按行分布(引文年份和L路径不算数)/认知灰度/身份共鸣/列表背靠背；扣主线句/推测标注；L4 六项（温度感·独特性·姿态·心流·叙事弧线·对立面承认）只报告人审不进评分 | 27 |

`gin-question` 的问题清单可以直接作为 `source-scan` 的 coverage 检查输入，**无需问用户"该写什么"，机器自己发现缺口**。答案卡经 `gin-outline` 重组为教程大纲，`gin-draft` 按大纲.json 逐章施工——写出的章是装配无关的构件，单篇教程和未来的书都从同一套章构件装配。

## 设计要点（全部来自实战踩坑）

- **六层资料地图**：L1 官方源 / L2 GitHub / L3 中文社区 / L4 英文社区 / L5 讨论区 / L6 学术
- **营销过滤是硬需求**：搜索噪音极大（减脂主题前 20 条一半微商软文），拒绝信号正则来自真实被拒样本
- **通道调度优先级**：域名黑名单（知乎等反爬站）> action 标注 > 扩展名；firecrawl 免 key 可单页采集，配 key 解锁整站扒取
- **失败先定性再处置**：`explain` 命令区分 配额耗尽/目标站封禁/JS 渲染墙/内容有效——不读输出就重试 = 浪费配额
- **学术镜像降级**：PubMed/PMC 被封自动经 Europe PMC 同 ID 镜像重采
- **语言政策**：教材级源（官方/学术）不限语言，媒体/UGC 按目标读者语言
- **冗余源不烧配额**：镜像/短讯类标 `redundant_with` 直接跳过

## 快速开始

```bash
# 0. 编排（推荐入口：资产认账 + 硬闸门 + 分批汇报）
cd xiejiaocheng
python3 scripts/flow_controller.py status --dir <tutorial工作目录>   # 各阶段产物/闸门状态
python3 scripts/flow_controller.py next --dir <d> --to stage3        # 放行校验（闸门+资产）

# 1. 发现（给主题词，跑六层枚举，产出 sources.json）
cd gin-tutorial-source-scan
python3 scripts/source_scan.py grade --title "..." --url "..."   # 逐条定级
python3 scripts/source_scan.py add --file sources.json --title "..." --url "..." \
    --layer L3 --lang zh --value high --note "价值说明" --action "单页采集"

# 2. 采集（配 key 后无配额限制）
echo '{"firecrawl_api_key": "fc-..."}' > ~/.config/gin-tutorial/config.yaml
cd gin-tutorial-harvest
python3 scripts/harvest.py harvest-one --dir <资料库目录> --url "<url>" --title "<标题>" --layer L3
python3 scripts/harvest.py manifest --dir <资料库目录> --topic "<主题>" --target-words 8000

# 3. 写作（按大纲.json 逐章施工，机检过了才出件）
cd gin-draft
python3 scripts/draft.py check --file <章.md> --materials <素材路径,逗号分隔> \
    --library <资料库目录> --case <贯穿案例名>
```

## 测试

```bash
python3 -m pytest xiejiaocheng/tests gin-question/tests gin-tutorial-source-scan/tests gin-tutorial-harvest/tests gin-answer/tests gin-outline/tests gin-draft/tests gin-qc/tests -q   # 212 passed
```

每个规则都有回归测试，样本来自 2026-09 减脂/力量训练两轮实战。
