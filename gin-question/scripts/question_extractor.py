#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""question_extractor.py — 从抓取的网页内容或搜索结果标题中提取真实问题。

要求：问题必须来自真实网页 title 或正文引用，不推断、不改写。
"""

import re
from html import unescape

from common import is_question_like, normalize_text


# 需要剔除的明显非问题模式（footer / 免责声明 / JS 代码 / 模板片段）
NON_QUESTION_PATTERNS = [
    r"本站有权",                          # 免责
    r"用户协议",
    r"隐私政策",
    r"免责声明",
    r"cookie",
    r"^[\s\W\d_]+$",                       # 纯符号
    r"^\s*$",
    r"window\.document",
    r"webdig\.js",
    r"\.js[\s？?]*$",
    r"^//",
    r"^[\(\)\{\};,\.\s]+",
    r"ICP备",                              # ICP 备案
    r"[一-龥]ICP备",              # 中文 ICP
    r"营业执照",
    r"友情链接",
    r"广告合作",
    r"联系我们",
    r"下载.*app",
    r"扫码下载",
    r"关注我们",
    r"订阅.*公众号",
    r"客服电话",
    r"工作时间",
    r"周一至周五",
    r"http[s]?://",                        # 链接
    r"www\.",
    r"\.com",
    r"\.cn",
    r"\.html",
    r"@",
    r"您访问的链接即将离开",                # 政府网站跳转提示
    r"是否继续",
    r"门户网站",
    r"访问.*即将",
    r"继续访问",
    r"您即将",
    r"温馨提示",
    r"使用.*浏览器",
    r"建议使用",
    r"分辨率",
    r"主办单位",
    r"承办单位",
    r"网站地图",
    r"返回首页",
    r"首页\s*>\s*",
    r"^\^[\s\d\.]+\s",                     # 维基百科脚注引用 ^ 7.0 7.1
    r"^\s*\^[\s一-龥]",                     # ^ 后跟中文（维基脚注引用）
    r"^[\^＊\*]+\s*[一-龥]",                 # 脚注符号 + 中文
    r"\[编辑\]",                            # 维基百科编辑按钮
    r"\[来源请求\]",
    r"^\s*受[^\n]{0,50}[？?]\s*$",           # 句子片段：受...感召？
    r"^\s*直到[^\n]{0,50}[？?]\s*$",         # 句子片段：直到...
    r"^\s*当[^\n]{0,50}[？?]\s*$",           # 句子片段：当...
    r"^[【《「][^】》」\n]{0,20}[？?]\s*$",   # 配对符号内 < 20 字符
    r"^.{0,40}[〈《].{0,15}[？?]\s*$",        # 含书名号 + 短片段（"在MV〈你好嗎？"）
    r"^[✕×✖✗✓✔]\s*[/\s]",                 # UI 关闭符号 + 注释
    r"^\s*[/\*]{1,2}.*[/\*]{1,2}\s*$",      # 代码注释 // /* */
    r"^.{0,30}\s+/\s+.{0,30}[？?]\s*$",      # 含 JS 注释 / 的 UI 提示
    r"Notion.{0,30}模板",                     # UI 推广 Notion 模板
    r"打包成.{0,30}模板",                      # UI 推广：打包成模板
    r"顺手收藏",                              # UI 操作提示
    r"点击查看",                              # UI 操作提示
    r"立即获取",                              # UI 操作提示
]

# 段落长度上限（超过视为正文片段而非问题）
MAX_QUESTION_LEN = 60

# 最小长度
MIN_QUESTION_LEN = 6


def strip_html(html):
    """简单去除 HTML 标签。"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text)


def is_obviously_not_question(text):
    """判断一段文本是否明显不是用户问题。"""
    t = text.strip()
    if len(t) < MIN_QUESTION_LEN:
        return True
    if len(t) > MAX_QUESTION_LEN:
        return True
    for pat in NON_QUESTION_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


# 核心减脂动作词——必须至少出现一个才算「减脂主题」
CORE_TERMS = [
    "减脂", "减肥", "减重", "瘦身", "瘦", "燃脂", "刷脂", "塑形", "塑身",
    "节食", "代餐", "轻食", "低脂",
]

# 主题相关词集合（按主题分类）—— 主题不同时使用不同集合
TOPIC_TERMS = {
    "减脂": CORE_TERMS,
    "一棵树": [
        "树", "树木", "乔木", "灌木", "藤本", "古树", "名木", "行道树", "观赏树",
        "用材林", "防护林", "经济林", "林木", "树苗", "苗木", "树苗",
        "银杏", "松树", "柏树", "槐树", "柳树", "杨树", "梧桐", "榕树",
        "桂花", "梅花", "桃花", "樱花", "海棠", "玉兰", "紫薇",
        "石榴", "柿子", "枣树", "桔树", "黄杨", "罗汉松",
        "树根", "树干", "树皮", "树叶", "树枝", "树冠", "树龄",
        "种植", "栽培", "修剪", "移栽", "养护", "施肥", "浇水",
        "光合作用", "落叶", "常绿", "针叶", "阔叶", "木本",
        "风水", "寓意", "庭院", "绿化",
    ],
    "新能源汽车": [
        "新能源", "电动汽车", "电车", "纯电", "混动", "插混", "增程",
        "电池", "续航", "充电", "快充", "慢充", "换电",
        "比亚迪", "特斯拉", "蔚来", "小鹏", "理想", "小米",
        "SU7", "Model", "BYD", "汉", "秦", "宋", "海豹",
    ],
    "周杰伦": [
        "周杰伦", "周董", "周导", "杰伦", "Jay", "杰迷", "周式",
        "小公举", "卤蛋", "小周周", "奶茶伦", "叶湘伦",
        "杰威尔", "JVR", "亚洲流行天王",
        "中国风", "Jay式情歌", "华语乐坛",
        "哎哟不错", "瞎啦", "屁啦",
        "不能说的秘密", "天台爱情", "满城尽带黄金甲",
        "稻香", "青花瓷", "晴天", "七里香", "夜曲", "东风破", "菊花台", "霍元甲",
        "范特西", "叶惠美", "十一月的萧邦", "依然范特西",
        "昆凌", "罗密欧", "海瑟薇", "小周周", " Hathaway ",
        "方文山", "黄俊郎", "钟兴民", "洪敬尧",
        "杰威尔音乐", "超级新人", "新人王",
        "周式", "周杰", "周董", "周女郎",
        "双截棍", "龙卷风", "简单爱",
        "百度", "百度百科", "百科", "维基", "wikipedia",
    ],
    "高血压": [
        "高血压", "Hypertension", "HBP", "HTN", "血压", "血压高",
        "降压", "降压药", "降压药", "血压高", "高血压病",
        "原发性高血压", "继发性高血压", "essential hypertension", "secondary hypertension",
        "白大衣高血压", "white coat", "白大衣",
        "隐匿性高血压", "masked hypertension", "隐蔽性",
        "难治性高血压", "resistant hypertension",
        "恶性高血压", "malignant hypertension",
        "妊娠高血压", "孕期高血压",
        "儿童高血压", "青少年高血压", "小儿高血压",
        "老年高血压", "老人高血压",
        "收缩压", "舒张压", "血压值", "血压计",
        "心率", "脉搏", "动脉", "血管",
        "高血压性心脏病", "高血压肾病", "高血压脑病",
        "脑卒中", "中风", "脑出血", "脑梗", "脑梗死",
        "冠心病", "心衰", "心力衰竭", "心梗", "心肌梗死",
        "动脉粥样硬化", "动脉硬化",
        "降压药", "ACEI", "ARB", "CCB", "利尿剂", "β受体阻滞剂",
        "硝苯地平", "氨氯地平", "缬沙坦", "厄贝沙坦", "美托洛尔",
        "倍他乐克", "拜新同", "代文", "络活喜",
        "高血压并发症", "靶器官损害",
        "低盐饮食", "限盐", "减重", "肥胖", "BMI",
        "高血压饮食", "高血压运动", "高血压禁忌",
        "高血压症状", "头痛", "头晕", "心悸", "耳鸣",
        "高血压遗传", "家族史", "高血压预防",
        "高血压标准", "高血压分级", "高血压诊断",
        "三高", "高血脂", "高血糖", "糖尿病",
    ],
    "时间管理": [
        "时间管理", "Time Management", "时间规划", "时间调度",
        "Scheduling", "GTD", "Getting Things Done", "戴维·艾伦", "David Allen",
        "番茄工作法", "Pomodoro", "番茄钟", "弗朗西斯科·西里洛", "Cirillo",
        "四象限", "艾森豪威尔矩阵", "Eisenhower Matrix", "史蒂芬·柯维", "Stephen Covey",
        "二八法则", "帕累托", "80/20", "Pareto",
        "SMART", "smart 原则",
        "时间块", "Time Blocking",
        "吃青蛙", "Eat That Frog", "博恩·崔西",
        "两分钟法则", "Two-minute Rule",
        "ABCDE", "艾维·利", "Ivy Lee",
        "柳比歇夫", "时间统计法",
        "高能要事", "重要紧急",
        "6点优先工作制",
        "康奈尔笔记", "Cornell",
        "聚光法则",
        "晨间日记", "佐藤传",
        "待办", "Todoist", "Trello", "Asana", "Notion",
        "专注", "专注力", "focus",
        "拖延", "拖延症", "Procrastination",
        "分心", "Distraction",
        "效率", "效能", "Productivity", "Efficiency",
        "优先级", "Priority",
        "截止", "Deadline", "DDL",
        "多任务", "单任务", "Multitask", "Single-task",
        "委托", "Delegate",
        "批量处理", "Batch Process",
        "职业倦怠", "Burnout",
        "上下文切换", "Context Switching",
        "时间审计", "Time Audit",
        "日程", "日历", "Calendar",
        "待办清单", "to-do",
        "碎片时间", "深度工作", "Deep Work",
        "晨间", "晚间", "黄金时间",
        "Excel", "GTD 软件", "时间追踪", "Toggl",
    ],
    "AI编程": [
        "AI编程", "AI Coding", "AI 辅助编程", "AI-Assisted Development", "AI 原生开发",
        "AI-Native Development", "对话式编程", "CHOP", "Chat-Oriented Programming",
        "氛围编程", "Vibe Coding", "Andrej Karpathy",
        "提示驱动开发", "Prompt-Driven Development", "生成式编程", "Generative Programming",
        "语音编程", "Speech-to-Code", "Addy Osmani",
        "伪代码", "Pseudocode", "SudoLang",
        "规约驱动", "Specification-Driven", "Dave Farley",
        "Coding Agent", "编程智能体", "IDE Copilot", "CLI Agent",
        "Inline IDE Assistant", "Chat Assistant", "Autonomous Development Loop",
        "Multi-Model Systems", "AI Pair Programmer",
        "RAG", "检索增强生成", "Retrieval-Augmented Generation",
        "MCP", "Model Context Protocol", "模型上下文协议",
        "Function Calling", "函数调用",
        "Agentic AI", "Agentic Coding", "智能体",
        "Context Window", "上下文窗口",
        "Prompt Engineering", "提示工程",
        "Zero-shot", "Few-shot", "零样本", "少样本",
        "Multi-file Editing", "Codebase Indexing",
        "Code Completion", "Code Generation", "Code Translation",
        "Code Review", "Sandboxing", "Telemetry",
        "Vector Database", "向量数据库", "Synthetic Data",
        "SWE-bench", "Cargo-Cult Programming",
        "GitHub Copilot", "Copilot", "微软", "Microsoft",
        "Cursor", "Anysphere",
        "Claude Code", "Anthropic", "Claude",
        "Windsurf", "Codeium", "Cognition", "Cascade",
        "Gemini Code Assist", "Google", "Antigravity",
        "Amazon Q Developer", "AWS", "Q Developer",
        "OpenAI Codex", "Codex", "OpenAI",
        "Tabnine", "Replit Ghostwriter", "Tabby",
        "OpenCode", "Anomaly", "Cline",
        "VS Code", "JetBrains", "PyCharm", "IntelliJ",
        "代码补全", "代码生成", "代码审查", "代码库索引",
        "Autonomy", "自主性", "Execution Environment", "执行环境",
        "Review Surface", "审查界面",
        "AGI", "大模型", "LLM", "GPT", "Claude", "Gemini", "Llama", "Qwen",
        "Prompt", "Token", "Embedding",
        "API", "SDK", "JSON", "YAML",
        "ChatGPT", "Claude.ai", "Gemini", "文心一言", "通义千问",
        "Agent", "智能体", "AutoGPT", "Devin",
        "Autonomous", "自主代理",
        "上下文", "上下文工程", "Context Engineering",
    ],
    "理财": [
        "理财", "Financial Management", "FM", "PFM", "WM", "FP", "IM", "AM",
        "个人理财", "Personal Finance", "财富管理", "Wealth Management",
        "财务规划", "Financial Planning", "投资规划", "Investment Planning",
        "资产配置", "Asset Allocation", "预算", "Budget",
        "Savings Account", "Checking Account", "储蓄账户", "支票账户",
        "Certificate of Deposit", "CD", "定期存款",
        "Mutual Fund", "共同基金", "基金", "股票", "Stock", "Bond", "债券",
        "Insurance", "保险",
        "ETF", "指数基金", "Exchange Traded Fund",
        "货币基金", "债券基金", "股票基金", "股票型基金", "混合基金",
        "Risk Tolerance", "风险承受能力", "Diversification", "分散投资",
        "Compound Interest", "复利",
        "Return on Investment", "ROI", "投资回报率",
        "Capital Gain", "Capital Loss", "资本利得", "资本损失",
        "Portfolio", "投资组合",
        "Financial Advisor", "财务顾问", "Robo-Advisor", "机器人顾问",
        "A股", "B股", "H股", "美股", "港股", "沪深300", "中证500", "上证指数", "深证成指",
        "K线", "均线", "成交量", "技术分析", "基本面分析", "价值投资", "巴菲特", "Buffett",
        "定投", "懒人理财", "定期定额",
        "资产配置派", "股债平衡", "核心+卫星",
        "散户", "韭菜", "割韭菜",
        "黑天鹅", "退市", "暴雷", "系统性风险",
        "复利", "复利效应",
        "存款", "储蓄", "活期", "定期", "大额存单",
        "国债", "逆回购", "货币市场",
        "P2P", "P2P爆雷", "庞氏骗局", "传销",
        "股市", "牛市", "熊市", "震荡市",
        "涨停", "跌停", "停牌", "复牌",
        "分红", "派息", "股息率",
        "市盈率", "PE", "市净率", "PB", "PEG",
        "指数", "宽基", "窄基",
        "QDII", "港股通", "沪港通", "深港通",
        "私募", "公募", "对冲基金", "Hedge Fund",
        "信托", "资管", "财富传承",
        "房地产", "REITs", "不动产",
        "黄金", "白银", "大宗商品", "原油", "外汇", "Forex",
        "比特币", "BTC", "以太坊", "ETH", "加密货币", "虚拟货币", "数字货币",
        "DeFi", "NFT", "Web3",
        "通货膨胀", "通缩", "CPI", "GDP", "美联储", "Fed", "加息", "降息",
        "理财小白", "月光族", "存款", "负债",
        "理财规划", "家庭资产", "资产负债表", "现金流",
        "应急资金", "备用金", "意外险",
        "退休金", "养老金", "社保",
        "教育金", "保险",
        "信用卡", "花呗", "借呗", "白条", "信用贷",
        "贷款", "房贷", "车贷", "经营贷",
        "投资风险", "投资骗局", "杀猪盘", "传销",
        "财商", "金融素养",
    ],
    "心理学": [
        "心理学", "Psychology", "心理", "Mental", "Mind",
        "Psyche", "Mental Health", "心理健康",
        "精神分析", "Psychoanalysis", "弗洛伊德", "Freud", "潜意识", "Unconscious",
        "潜意识", "Subconscious", "本我", "Id", "自我", "Ego", "超我", "Superego",
        "梦的解析", "Interpretation of Dreams", "梦境",
        "行为主义", "Behaviorism", "华生", "Watson", "斯金纳", "Skinner",
        "条件反射", "Classical Conditioning", "操作性条件反射", "Operant Conditioning",
        "人本主义", "Humanistic", "马斯洛", "Maslow", "罗杰斯", "Rogers",
        "自我实现", "Self-actualization", "需求层次", "Hierarchy of Needs",
        "认知心理学", "Cognitive Psychology", "奈瑟", "Neisser", "西蒙", "Simon",
        "认知", "Cognition", "认知偏差", "Cognitive Bias",
        "构造主义", "Structuralism", "冯特", "Wundt", "铁钦纳", "Titchener",
        "机能主义", "Functionalism", "詹姆斯", "James", "杜威", "Dewey",
        "格式塔", "Gestalt", "韦特海默", "Wertheimer", "科勒", "Kohler",
        "整体大于部分之和", "Whole is greater than the sum",
        "深度心理学", "Depth Psychology", "荣格", "Jung",
        "原型", "Archetype", "集体无意识", "Collective Unconscious",
        "阴影", "Shadow", "阿尼玛", "Anima", "阿尼姆斯", "Animus",
        "自我心理学", "Ego Psychology",
        "新精神分析", "Neo-Freudian", "Neo-Psychoanalysis", "霍妮", "Horney",
        "沙利文", "Sullivan", "阿德勒", "Adler", "自卑感", "Inferiority",
        "社会心理学", "Social Psychology", "戴维·迈尔斯", "Myers",
        "发展心理学", "Developmental Psychology", "皮亚杰", "Piaget",
        "认知发展", "Cognitive Development", "维果茨基", "Vygotsky",
        "依恋理论", "Attachment Theory", "鲍尔比", "Bowlby", "安斯沃斯", "Ainsworth",
        "人格心理学", "Personality Psychology", "大五人格", "Big Five",
        "MBTI", "迈尔斯-布里格斯", "Myers-Briggs",
        "九型人格", "Enneagram",
        "积极心理学", "Positive Psychology", "心流", "Flow",
        "临床心理学", "Clinical Psychology", "咨询心理学", "Counseling Psychology",
        "变态心理学", "Abnormal Psychology", "病理心理学",
        "社会工作", "Social Work",
        "心理治疗", "Psychotherapy", "心理咨询", "Counseling",
        "认知行为治疗", "CBT", "Cognitive Behavioral Therapy",
        "辩证行为治疗", "DBT", "Dialectical Behavior Therapy",
        "精神分析治疗", "Psychoanalytic Therapy",
        "暴露疗法", "Exposure Therapy",
        "系统脱敏", "Systematic Desensitization",
        "正念", "Mindfulness", "冥想", "Meditation",
        "催眠", "Hypnosis", "暗示", "Suggestion",
        "焦虑", "Anxiety", "抑郁", "Depression", "失眠", "Insomnia",
        "恐惧症", "Phobia", "强迫症", "OCD", "PTSD", "创伤后应激",
        "双相", "Bipolar", "自闭症", "Autism", "ADHD", "多动症",
        "抑郁", "抑郁症", "躁狂", "焦虑症", "社交焦虑",
        "依恋类型", "安全型", "焦虑型", "回避型",
        "童年创伤", "原生家庭", "Family of Origin",
        "代际创伤", "代际传递",
        "依恋", "Attachment", "分离焦虑",
        "共情", "Empathy", "同情", "Sympathy",
        "情商", "EQ", "Emotional Intelligence", "情绪智力",
        "情绪", "Emotion", "情感", "Affection",
        "压力", "Stress", "焦虑源", "应激",
        "应对", "Coping", "防御机制", "Defense Mechanism",
        "压抑", "Repression", "投射", "Projection", "否认", "Denial",
        "合理化", "Rationalization", "升华", "Sublimation",
        "性格", "Character", "气质", "Temperament",
        "内向", "外向", "Introvert", "Extrovert",
        "高敏感", "HSP", "Highly Sensitive Person",
        "讨好型人格", "People Pleaser", "回避型人格",
        "完美主义", "Perfectionism",
        "拖延症", "Procrastination",
        "PTSD", "创伤", "Trauma",
        "原生家庭", "Family of Origin",
        "童年阴影", "Inner Child",
        "自我", "Self", "本我", "Superego",
        "潜意识", "Subconscious",
        "情绪管理", "Emotion Regulation",
        "依恋", "依恋类型",
        "亲密关系", "Intimate Relationship", "依恋理论",
        "共情", "Empathy",
        "梦", "Dream", "梦境分析",
    ],
    "美食": [
        "美食", "Food", "Cuisine", "Gastronomy", "菜系",
        "风味流派", "帮菜", "中餐", "Chinese Food", "中华料理",
        "鲁菜", "山东菜", "齐鲁风味", "Shandong Cuisine",
        "川菜", "四川菜", "巴蜀菜", "Sichuan Cuisine",
        "粤菜", "广东菜", "岭南菜", "Cantonese Cuisine",
        "苏菜", "江苏菜", "淮扬菜", "金陵菜", "Huaiyang Cuisine",
        "闽菜", "福建菜", "Fujian Cuisine", "Min Cuisine",
        "浙菜", "浙江菜", "Zhejiang Cuisine",
        "湘菜", "湖南菜", "Hunan Cuisine",
        "徽菜", "徽州菜", "Anhui Cuisine", "Hui Cuisine",
        "京菜", "北京菜", "京鲁菜", "津菜", "天津菜",
        "豫菜", "河南菜", "冀菜", "河北菜",
        "东北菜", "赣菜", "江西菜", "客家菜",
        "本帮菜", "上海菜", "Shanghainese Cuisine",
        "八大菜系", "四大菜系", "十大菜系", "十二大菜系",
        "中式烹饪", "中式点心", "家常菜", "私房菜",
        "甜", "咸", "酸", "辣", "苦", "香", "鲜", "麻",
        "麻辣", "香辣", "酸辣", "甜辣", "鱼香", "宫保", "怪味", "椒麻",
        "葱烧", "红烧", "清蒸", "白灼", "糖醋", "红焖", "蒜蓉", "酱爆",
        "火锅", "Hot Pot", "麻辣火锅", "鸳鸯锅", "九宫格", "川渝火锅", "潮汕牛肉火锅",
        "烧烤", "BBQ", "烤串", "撸串",
        "小龙虾", "麻辣小龙虾", "Crayfish",
        "粤式早茶", "早茶", "茶点", "广式早茶",
        "点心", "Dim Sum", "包子", "饺子", "馄饨", "烧麦", "虾饺", "肠粉", "糯米鸡",
        "月饼", "汤圆", "粽子", "青团", "年糕", "冰皮月饼",
        "面食", "面条", "拉面", "刀削面", "热干面", "重庆小面", "兰州拉面", "炸酱面",
        "米饭", "白米饭", "蛋炒饭", "扬州炒饭",
        "粥", "白粥", "皮蛋瘦肉粥", "小米粥",
        "米线", "过桥米线", "螺蛳粉", "酸辣粉", "桂林米粉",
        "食材", "配料", "调料", "盐", "糖", "油", "醋", "酱油", "老抽", "生抽",
        "辣椒", "花椒", "麻椒", "胡椒", "姜", "蒜", "葱",
        "豆瓣酱", "甜面酱", "海鲜酱", "XO酱",
        "米其林", "必吃榜", "米其林餐厅", "黑珍珠",
        "外卖", "美团", "饿了么",
        "网红", "探店", "夜宵", "深夜食堂", "路边摊", "大排档",
        "茶", "Tea", "普洱", "龙井", "铁观音", "大红袍", "白茶",
        "酒", "白酒", "黄酒", "葡萄酒", "啤酒", "清酒",
        "咖啡", "Coffee", "拿铁", "美式", "卡布奇诺", "手冲",
        "奶茶", "喜茶", "奈雪", "蜜雪冰城",
        "寿司", "Sushi", "刺身", "天妇罗", "日式",
        "披萨", "Pizza", "汉堡", "意面", "Pasta",
        "西餐", "日料", "韩餐", "东南亚菜", "法餐", "意餐", "分子料理",
        "国宴", "官府菜", "宫廷菜", "中华料理",
        "北京烤鸭", "麻婆豆腐", "宫保鸡丁", "回锅肉", "鱼香肉丝", "水煮鱼",
        "白切鸡", "烧鹅", "佛跳墙", "西湖醋鱼", "龙井虾仁", "东坡肉",
        "剁椒鱼头", "臭鳜鱼", "松鼠鳜鱼", "狮子头", "文思豆腐",
        "辣椒", "花椒", "麻椒",
        "舌尖上的中国", "风味人间", "人生一串", "早餐中国",
        "肯德基", "KFC", "麦当劳", "McDonald's", "星巴克", "Starbucks",
        "必胜客", "Pizza Hut",
    ],
}


def is_relevant(text, topic=None):
    """判断问题是否与指定主题相关。

    topic 为 None 时使用减脂核心词。
    要求：至少出现一个核心词。
    """
    terms = TOPIC_TERMS.get(topic, CORE_TERMS)
    if any(w in text for w in terms):
        return True
    return False

# 辅助相关词——单独不够，但配合核心词可提高相关度
AUX_TERMS = [
    "体脂", "体脂率", "热量", "卡路里", "大卡", "千卡", "千焦",
    "生酮", "低碳", "辟谷", "暴食", "厌食", "食欲", "饱腹",
    "BMI", "腰围", "围度", "肌肉", "增肌",
    "经期", "姨妈", "月经", "例假", "生理期",
    "平台期", "瓶颈", "反弹", "复胖",
    "健身房", "跑步", "HIIT", "心率",
    "骗局", "智商税", "伪科学", "偏方",
    "上班族", "久坐",
    "夜宵", "奶茶", "火锅",
    "蛋白质", "蛋白",
]


# 反问/引导/非真实用户提问模式
RHETORICAL_PATTERNS = [
    r"^你(见过|知道|是否|有没有|觉得|认为|想不想)",
    r"你.*(?:看着|心动|中招|遭遇)",
    r"你的(?:心动|学校|公司|城市)",
    r"^揭示.*你是否",
    r"^看看你是否",
    r"^你是否曾经",
    r"^你是否遭遇过这种困惑",
    r"^还在.*(?:节食|减重|减肥|减脂).*？$",
    r"^.*是不是一直.*犯迷糊",
    r"^很多人在.*一定会出现.*现象",
    r"^减重容易维持难？$",
    r"^想一想你真正想要的是什么",
]


def clean_question_text(text):
    """清洗问题文本中的 markdown、UI、元数据等残留碎片。

    返回清洗后的文本；如果清洗后明显不是真实用户问题，返回空字符串。
    """
    if not text:
        return ""

    # 1. 去掉转义换行和真实换行，统一为空格
    text = text.replace("\\n", "\n")
    text = re.sub(r"\s+", " ", text)

    # 2. 去掉 markdown 格式符号
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+", "", text)

    # 3. 去掉表情符号（常用 Unicode 表情范围）
    text = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+", "", text)

    # 3b. 去掉列表/强调符号及其前面的残缺前缀（如“俯卧撑练的是胸 ‼️节食减肥更快？”）
    text = re.sub(r"^[^·•‼️]*[·•‼️]\s*", "", text)

    # 3c. 去掉剩余营销号常用特殊符号（双叹号 ‼️、加重号 · • 等）
    text = re.sub(r"[‼️‼·•⚠️✅❌]+", "", text)

    # 4. 去掉日期、作者、来源、编辑等元数据
    text = re.sub(r"\d{4}-\d{2}-\d{2}\s*", "", text)
    text = re.sub(r"(作者|来源|编辑|整理|记者)[：:][^、,，；;:.。！?？\s]+\s*[、,]?", "", text)

    # 5. 去掉社交媒体/评论区用户名残留（用户名 + 数字/赞）
    text = re.sub(r"^\s*\S+?\s+(?:\d+|赞)\s+", "", text)
    text = re.sub(r"^\s*帐号已注销\s*", "", text)

    # 6. 去掉开头残缺的分隔符和括号
    text = re.sub(r"^\s*[：:、,，；;\.\s\[\（\(]+", "", text)
    text = re.sub(r"\s*[\]\）\)]\s*$", "", text)

    # 7. 去掉末尾数字编号
    text = re.sub(r"\s*\d+\s*$", "", text)

    text = text.strip()
    return text


def is_real_user_question(text):
    """判断清洗后的问题是否是真实用户提出的求知性问题。

    返回 False 的常见情况：
    - 反问/引导句
    - 文章章节标题
    - 营销号开头引导语
    - 过短或明显残缺
    """
    if not text or len(text) < 6:
        return False

    # 反问/引导模式
    for pat in RHETORICAL_PATTERNS:
        if re.search(pat, text):
            return False

    # 文章/营销号引导语
    guide_prefixes = [
        "你是否曾经",
        "你是否遭遇过",
        "看看你是否",
        "揭示",
        "你有没有想过",
        "你还在",
        "关注健康生活新范式",
        "最热内容",
    ]
    for prefix in guide_prefixes:
        if text.startswith(prefix):
            return False

    return True


def clean_tail(text):
    """清理问题末尾的站点名 / 展开 / 分隔符尾巴。"""
    text = re.sub(r"\s*[\-–—|]\s*(民福康|百度|百度健康|薄荷|家庭医生在线|知乎|简书|新浪|网易|腾讯|凤凰|搜狐|健康之路|三九养生堂|99健康|39健康|寻医问药|杏林普康|好大夫|丁香医生|百度百科|百度文库|湖南省林业局|安徽省林业局|国家林业和草原局|北京市园林绿化局|科普中国|生命教育|问诊|林业局)\s*$", "", text)
    text = re.sub(r"\s*展开\s*$", "", text)
    text = re.sub(r"\s*收起\s*$", "", text)
    text = re.sub(r"\s*[\.]{3,}\s*$", "", text)
    text = re.sub(r"\s*[\-–—\|]+\s*$", "", text)
    text = text.strip()
    return text


def clean_head(text):
    """清理问题开头的引述/反问/前缀。"""
    # 去掉前后成对引号
    text = text.strip()
    # 成对引号（含英文/中文/日文 + Unicode 引号）
    pairs = [
        ('"', '"'), ('“', '”'),  # 直双引号 + 弯双引号
        ("'", "'"), ('‘', '’'),  # 直单引号 + 弯单引号
        ('「', '」'), ('『', '』'),
        ('《', '》'),
        ('(', ')'), ('（', '）'),
    ]
    for l, r in pairs:
        if text.startswith(l) and text.endswith(r):
            text = text[1:-1].strip()
            break
    # 去掉单边残留引号
    text = re.sub(r'^[「『《"\'\(]+', '', text)
    text = re.sub(r'[」』》"\'\)]+$', '', text)
    # 去掉常见反问/引述前缀
    text = re.sub(
        r"^(可是|但是|然而|不过|那么|反之|若是|如果|因为|由于|虽然|尽管|其实|实际上|不夸张地说|有人会说|有人说|商家说|我们说|据说|据悉|笔者|笔者认为|笔者觉得|笔者通过|笔者结合|笔者在|作者认为|有人认为|有人说|很多人说|据了解|据专家|据介绍|据悉)",
        "", text)
    # 去掉括号式作者/出处前缀：例如 "【光明图片】xxx"
    text = re.sub(r"^【[^】]*】", "", text)
    # 去掉"作者：xxx" "来源：xxx"
    text = re.sub(r"^(作者|来源|编辑|记者|笔者|整理|摘录)[：:][^。]+[。,]?\s*", "", text)
    # 去掉本站/标签前缀
    text = re.sub(r"^(此刻新闻|热点新闻|首页|推荐|热门|专题|正文|导读|摘要)[：:、\s]*", "", text)
    # 去掉导航前缀
    text = re.sub(r"^(上一篇|下一篇|上一条|下一条|相关阅读|延伸阅读|相关推荐|推荐阅读|猜你喜欢)[：:、\s]*", "", text)
    # 去掉 FAQ 标记前缀（多轮，直到无变化）
    for _ in range(5):
        prev = text
        # 多种常见 FAQ/导航/章节前缀
        text = re.sub(
            r"^(常见问题FAQ|常见问题|FAQ|问题|问|Q&A|Q|A|目录|章节|章|节|第\d+[章节]|Chapter|Topic)"
            r"[：:、\.\s]+",
            "", text)
        # 数字编号前缀
        text = re.sub(r"^\d{1,3}[、\.\)\s]+", "", text)
        if text == prev:
            break
    # 中文数字编号前缀：一、二、三、（一）(一)
    text = re.sub(r"^[（(]?[一二三四五六七八九十百零]+[）)]?[、\.\s]+", "", text)
    # 列表符号前缀：· • ● ○ ▪ ▫
    text = re.sub(r"^[·•●○▪▫\-\*•]+\s*", "", text)
    # 「人民号平台下载客户端」等客户端前缀
    text = re.sub(r"^(人民号平台下载客户端|客户端|下载.*客户端|打开.*App|扫码下载|扫码关注|关注我们)", "", text)
    # 参考资料
    text = re.sub(r"^参考资料[：:]\s*", "", text)
    text = re.sub(r"\[\d+\]", "", text)  # [1] [2] 引用标记
    # 去掉陈述句前缀：所以 / 因此 / 总之 / 综合 / 看来 / 也就是说 / 简单来说
    text = re.sub(r"^(所以|因此|总之|综合|看来|也就是说|简单来说|简言之|换言之|其实|可见到|结果|可见|那么说|看得出来)[，,\s]*", "", text)
    # 去掉逗号/顿号开头的残缺
    text = re.sub(r"^[，,、；;:\s]+", "", text)
    # 去掉末尾残留的"?"、"？"前后多余空格
    text = text.strip()
    return text


def extract_from_title(title, topic=None):
    """从页面标题中提取问题。"""
    if not title:
        return None
    title = title.strip()
    # 去掉常见的后缀，如 " - 知乎"
    title = re.sub(r"[\-–—]\s*(知乎|百度知道|Quora|Reddit|豆瓣|悟空问答|简书).*$", "", title).strip()
    title = title.strip()
    title = clean_tail(title)
    title = clean_head(title)
    if is_obviously_not_question(title):
        return None
    # 标题也要求严格：问号/吗/呢结尾
    if not (title.endswith("？") or title.endswith("?") or title.endswith("吗") or title.endswith("呢")):
        return None
    if is_question_like(title):
        normalized = normalize_text(title)
        if is_relevant(normalized, topic=topic):
            if not is_real_user_question(normalized):
                return None
            return normalized
    return None


def extract_from_content(html, source_url, topic=None, max_candidates=50):
    """从 HTML 正文中提取候选问题。

    策略：
    - 从 h1/h2/h3 标题、加粗文本、独立段落中提取疑问句
    - 优先提取看起来像用户提问的句子
    - 剔除明显非问题模式（footer / 免责 / JS）
    """
    text = strip_html(html)
    candidates = []

    # 1. 提取 h1-h3 中的文本
    headings = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.DOTALL)
    for h in headings:
        h = strip_html(h).strip()
        q = extract_from_title(h, topic=topic)
        if q and q not in candidates:
            candidates.append(q)

    # 2. 按句子切分，提取疑问句
    # 在 。！？? \n 以及各种成对引号/括号后切分
    sentences = re.split(r"(?<=[。！？?\n“”‘’「」『』()（）])", text)
    for s in sentences:
        s = s.strip()
        if is_obviously_not_question(s):
            continue
        # 严格过滤：必须以问号、问号词结尾
        if not (s.endswith("？") or s.endswith("?") or s.endswith("吗") or s.endswith("呢") or s.endswith("啊？") or s.endswith("？")):
            continue
        if is_question_like(s):
            q = normalize_text(s)
            q = clean_question_text(q)
            if not q:
                continue
            if not is_real_user_question(q):
                continue
            q = clean_tail(q)
            q = clean_head(q)
            if not is_relevant(q, topic=topic):
                continue
            if q not in candidates:
                candidates.append(q)
        if len(candidates) >= max_candidates:
            break

    return [{"text": q, "source_url": source_url, "extracted_from": "content"} for q in candidates]


def extract_from_search_result(title, url, topic=None):
    """当页面无法抓取时，使用搜索结果的页面标题作为问题来源。"""
    q = extract_from_title(title, topic=topic)
    if q:
        return {"text": q, "source_url": url, "extracted_from": "search_title"}
    return None


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 question_extractor.py <html-file-or-title> [--title]")
        sys.exit(1)
    arg = sys.argv[1]
    is_title = "--title" in sys.argv
    if is_title:
        print(extract_from_title(arg))
    else:
        try:
            with open(arg, "r", encoding="utf-8") as f:
                html = f.read()
        except Exception:
            html = arg
        results = extract_from_content(html, "https://example.com")
        for r in results[:10]:
            print(r["text"])


if __name__ == "__main__":
    main()
