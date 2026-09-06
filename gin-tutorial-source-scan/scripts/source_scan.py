#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""source_scan.py — 教程资料源发现层的工具脚本（质量分级/层级分类/收敛/清单管理）。

分工：搜索动作由 Agent 完成（tavily CLI 或 WebSearch 工具），本脚本负责
判断与记录——给搜索结果定级、分类、去重落盘、收敛判定、覆盖度检查。
规则来自 9/2 减脂实测的真实噪音样本（微商软文/电商 SEO 农场占搜索结果一半）。

用法：
    python3 source_scan.py grade --title "..." --url "..." [--snippet "..."]
    python3 source_scan.py add --file sources.json --title "..." --url "..." --layer L3 --lang zh --value medium --note "..."
    python3 source_scan.py reject --file sources.json --title "..." --url "..." --reason "..."
    python3 source_scan.py coverage --file sources.json --questions "减脂原理,饮食方案"
    python3 source_scan.py init-config [--tavily-key KEY]
    python3 source_scan.py channel          # 当前搜索通道：tavily / agent-websearch
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse, urlunparse

CONFIG_PATH = os.path.expanduser("~/.config/gin-tutorial/config.yaml")

# ---------- 质量分级 ----------

# 拒绝信号（任一命中即拒绝，优先级最高）
MLM_KEYWORDS = ["加盟", "代理", "月入", "躺赚", "正品", "旗舰店", "官网直销", "多少钱",
                "价格表", "优惠价", "购买链接", "加微信", "加V", "微商", "厂家直销"]
ECOMMERCE_HOSTS = ("item.taobao.com", "detail.tmall.com", "item.jd.com", "1688.com",
                   "amazon.", "/dp/", "yangkeduo.com", "pinduoduo")
# 产品营销文话术（9/2 实测样本归纳）：蹭「原理」但卖「效果」
PRODUCT_PITCH = re.compile(r"(原理|科普).{0,6}(效果|功效|怎么样|有用吗|骗局|曝光)")
BRAND_DOT = re.compile(r"[A-Za-z0-9]{2,}·")           # MOOSOR·9S小魔原理分析
SLIM_PRODUCT = re.compile(r"(咖啡|普洱茶|减肥茶|酵素|代餐奶昔).{0,8}(减脂|减肥|瘦身)")

# 高价值信号
HIGH_HOST_PATTERNS = [
    ".gov", ".gov.cn", ".edu", "who.int", "cdc.gov", "un.org", "unesco.org",
    "nhc.gov.cn", "mayoclinic.org",        # mayoclinic 归 medium？不——宿主强背书归 high，措辞见下
    "arxiv.org", "sciencedirect.com", "ncbi.nlm.nih.gov", "pubmed", "nature.com",
    "chinacdc.cn", "cdc.cn",   # 中国疾控中心（9/5 减脂实测：chinacdc.cn 曾误判 unknown）
    "cell.com", "nejm.org", "doi.org", "semanticsscholar.org",
]
MEDIUM_HOSTS = ["mayoclinic.org", "issaonline.com", "healthline.com", "webmd.com",
                "verywellfit.com", "myfitnesspal.com"]


def _host(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def grade_source(title, url, snippet=""):
    """返回 (value, reason)。value ∈ high/medium/unknown/reject。"""
    text = "%s %s %s" % (title, url, snippet or "")
    host = _host(url)

    # 1) 拒绝信号（硬规则，不可被高价值信号覆盖）
    if any(k in text for k in MLM_KEYWORDS):
        return "reject", "营销/拉人头话术命中"
    if any(h in host or h in url for h in ECOMMERCE_HOSTS):
        return "reject", "电商商品页，非教材"
    if PRODUCT_PITCH.search(title):
        return "reject", "产品营销文：蹭原理卖效果"
    if BRAND_DOT.search(title) and ("原理" in title or "分析" in title):
        return "reject", "品牌+原理分析话术，产品软文特征"
    if SLIM_PRODUCT.search(title):
        return "reject", "单品减脂 SEO 内容农场"

    # 2) 高价值信号
    if any(p in host for p in HIGH_HOST_PATTERNS) and not any(m in host for m in MEDIUM_HOSTS):
        return "high", "官方/学术/权威医疗源"
    if host.startswith("docs.") or "/docs/" in url:
        return "high", "结构化文档站（可整站采集）"

    # 3) 中等信号
    if any(m in host for m in MEDIUM_HOSTS):
        return "medium", "认证机构/医学科普媒体"
    if re.search(r"\.(pdf|epub)(\?|$)", url.lower()):
        return "medium", "实操文档（PDF），有真实细节待核"
    if re.search(r"(blog|post|article)", host + url):
        return "medium", "个人/机构博客，经验类内容"

    # 4) 默认
    return "unknown", "无明确信号，需人工/Agent 复核内容"


# ---------- 六层资料地图 ----------

LAYER_RULES = [
    ("L1", lambda h: any(p in h for p in [".gov", ".edu", "who.int", "cdc.gov", "un.org"]) or h.startswith("docs.")),
    ("L6", lambda h: any(p in h for p in ["arxiv.org", "semanticscholar.org", "sciencedirect.com",
                                          "ncbi.nlm.nih.gov", "pubmed", "nature.com", "doi.org",
                                          "researchgate.net", "springer.com", "cell.com"])),
    ("L2", lambda h: h == "github.com" or h.endswith(".github.io") or h == "gitee.com"),
    ("L3", lambda h: any(p in h for p in ["zhihu.com", "juejin.cn", "sspai.com", "csdn.net",
                                          "jianshu.com", "weixin.qq.com", "mp.weixin.qq.com",
                                          "oschina.net", "segmentfault.com", "163.com", "zhihu.column"])),
    ("L4", lambda h: any(p in h for p in ["medium.com", "dev.to", "substack.com", "hashnode.dev",
                                          "freecodecamp.org"])),
    ("L5", lambda h: any(p in h for p in ["reddit.com", "news.ycombinator.com", "v2ex.com",
                                          "linux.do", "x.com", "twitter.com", "lobste.rs"])),
]


def classify_layer(url):
    host = _host(url)
    for layer, pred in LAYER_RULES:
        if pred(host):
            return layer
    return "L3"  # 默认按中文社区处理（搜索以中文为主时的最大概率层）


# ---------- 收敛信号 ----------

def is_saturated(seen, round_total):
    """一轮搜索前 round_total 条中已有 seen 条收录 → 池子饱和（≥3/10 即收敛）。"""
    return round_total > 0 and seen >= 3 and seen / round_total >= 0.3


# ---------- sources.json 管理 ----------

def _normalize_url(url):
    """去 utm 参数、fragment、尾部斜杠——同一页面不同分享链接视为同一源。"""
    p = urlparse(url)
    query = "&".join(q for q in p.query.split("&") if not q.startswith("utm_"))
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc.lower(), path, "", query, ""))


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_source(path, entry):
    """收录一条来源（按规范化 URL 去重）。已存在则忽略，返回是否新增。"""
    data = _load(path)
    norm = _normalize_url(entry["url"])
    for s in data["sources"]:
        if _normalize_url(s["url"]) == norm:
            return False
    entry["url"] = entry["url"]
    entry.setdefault("action", "单页采集")
    data["sources"].append(entry)
    _save(path, data)
    return True


def add_rejected(path, entry):
    data = _load(path)
    data.setdefault("rejected", []).append(entry)
    _save(path, data)


def coverage_report(path, questions):
    """每个 TOP 高频问题有几份独立来源覆盖（按 note 关键词粗配）。"""
    data = _load(path)
    notes = " ".join(s.get("note", "") + " " + s.get("title", "") for s in data["sources"])
    counts = {q: len([1 for s in data["sources"]
                      if q in (s.get("note", "") + s.get("title", ""))]) for q in questions}
    gap = "、".join(q for q, c in counts.items() if c == 0) or "无"
    return {"高频问题": questions, "已覆盖来源数": counts, "gap": gap}


# ---------- 配置（训记模式：~/.config/gin-tutorial/config.yaml，JSON 内容） ----------

def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def search_channel():
    """tavily = 已配置 API key（脚本/Agent 调 tavily CLI）；
    agent-websearch = 无 key，由 Agent 用 WebSearch 工具执行搜索。"""
    return "tavily" if load_config().get("tavily_api_key") else "agent-websearch"


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="教程资料源发现层工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grade", help="给一条搜索结果定级")
    g.add_argument("--title", required=True)
    g.add_argument("--url", required=True)
    g.add_argument("--snippet", default="")

    a = sub.add_parser("add", help="收录来源")
    a.add_argument("--file", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--url", required=True)
    a.add_argument("--layer", required=True)
    a.add_argument("--lang", default="zh")
    a.add_argument("--value", required=True)
    a.add_argument("--note", default="")
    a.add_argument("--action", default="单页采集")
    a.add_argument("--redundant-with", default=None,
                   help="冗余源标记：本源与某已收录源同内容时填其 URL，harvest 层跳过不采")

    r = sub.add_parser("reject", help="记录拒绝")
    r.add_argument("--file", required=True)
    r.add_argument("--title", required=True)
    r.add_argument("--url", default="")
    r.add_argument("--reason", required=True)

    c = sub.add_parser("coverage", help="覆盖度检查")
    c.add_argument("--file", required=True)
    c.add_argument("--questions", required=True, help="逗号分隔的高频问题清单")

    ic = sub.add_parser("init-config", help="写入/更新 API key 配置")
    ic.add_argument("--tavily-key", default=None)

    sub.add_parser("channel", help="显示当前搜索通道")

    args = ap.parse_args()

    if args.cmd == "grade":
        v, reason = grade_source(args.title, args.url, args.snippet)
        print(json.dumps({"value": v, "reason": reason}, ensure_ascii=False))
    elif args.cmd == "add":
        entry = {"title": args.title, "url": args.url, "layer": args.layer,
                 "lang": args.lang, "value": args.value, "note": args.note,
                 "action": args.action}
        if args.redundant_with:
            entry["redundant_with"] = args.redundant_with
        added = add_source(args.file, entry)
        print(json.dumps({"added": added}, ensure_ascii=False))
    elif args.cmd == "reject":
        add_rejected(args.file, {"title": args.title, "url": args.url, "reason": args.reason})
        print(json.dumps({"recorded": True}, ensure_ascii=False))
    elif args.cmd == "coverage":
        print(json.dumps(coverage_report(args.file, args.questions.split(",")), ensure_ascii=False, indent=2))
    elif args.cmd == "init-config":
        cfg = load_config()
        if args.tavily_key:
            cfg["tavily_api_key"] = args.tavily_key
        save_config(cfg)
        print(json.dumps({"config": CONFIG_PATH, "channel": search_channel()}, ensure_ascii=False))
    elif args.cmd == "channel":
        print(search_channel())


if __name__ == "__main__":
    main()
