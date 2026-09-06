#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest.py — 教程采集层的工具脚本（通道调度/后处理/内容验收/落盘/manifest）。

分工：采集动作由 Agent 完成（调 firecrawl CLI / opencli / collector），
本脚本负责判断与记录——决定每个 URL 走哪个通道、剥掉站内锚点噪音、
校验正文是否够料、生成 coverage-manifest.json。
规则来自 9/2-9/3 减脂/力量训练实测：
- Docusaurus 标题锚点 [](url "直接链接") 占文件 3/4 体积 → 剥
- 外部引用链接是溯源线索 → 保留
- 正文 <500 中文字 = 抓到导航页/空页 → 判失败
- 知乎对 datacenter IP 反爬 → 域名黑名单优先于 action 标注

用法：
    python3 harvest.py channel --url "..." --action "单页采集"
    python3 harvest.py postprocess --file a.md [--site-host docs.x.com]
    python3 harvest.py validate --file a.md [--min-chars 500]
    python3 harvest.py manifest --dir <输出目录> --topic "..." [--target-words 8000]
"""
import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

# ---------- 通道调度 ----------

# 域名黑名单：反爬/登录墙站点，必须真实浏览器，firecrawl 必撞验证码。
# 匹配规则：netloc == h 或 netloc 以 ".h" 结尾（防 example-x.com 误伤）
OPENCLI_HOSTS = ("zhihu.com", "weibo.com", "x.com",
                 "twitter.com", "linux.do")
# 路径级黑名单：B站专栏走 opencli，B站视频走 collector，按域名分不开
OPENCLI_PATHS = ("bilibili.com/read",)
# collector 通道：PDF / 公众号 / 视频页
COLLECTOR_HINTS = (".pdf", "mp.weixin.qq.com", "youtube.com", "bilibili.com/video",
                   "b23.tv")
BOOK_ACTIONS = ("找电子版/购书",)
DOWNLOAD_ACTIONS = ("整站扒取",)


def pick_channel(url, action, firecrawl_available=True):
    """返回通道：firecrawl-scrape / firecrawl-download / opencli / collector / skip-book。

    优先级：域名黑名单 > action 标注 > 扩展名 > 默认。
    firecrawl_available=False 时 firecrawl-download 降级为 firecrawl-scrape
    （download 需要 key，scrape 免 key）。
    """
    netloc = urlparse(url).netloc.lower()
    host = (netloc + urlparse(url).path).lower()

    # 1) 黑名单最优先——action 标错也不能硬撞反爬。
    #    域名匹配用真后缀（example-x.com 不得误伤 x.com）
    if any(netloc == h or netloc.endswith("." + h) for h in OPENCLI_HOSTS):
        return "opencli"
    if any(h in host for h in OPENCLI_PATHS):
        return "opencli"

    # 2) action 显式标注
    if action in BOOK_ACTIONS:
        return "skip-book"
    if action in DOWNLOAD_ACTIONS:
        return "firecrawl-download" if firecrawl_available else "firecrawl-scrape"

    # 3) 扩展名/内容类型
    if any(h in host for h in COLLECTOR_HINTS):
        return "collector"

    # 4) 默认
    return "firecrawl-scrape"


# ---------- 后处理 ----------

# Markdown 链接 [text](url "title")，text 可空（Docusaurus 锚点）
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _host_of(url):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def postprocess_markdown(text, site_host=None):
    """剥站内链接噪音，保留外部引用链接。

    - 空显示文本的锚点 [](url "…")：整段移除
    - 站内链接 [text](site-url)：剥 URL 留 text（阅读流不断）
    - 外部链接：原样保留（溯源线索）
    - site_host=None：不剥任何 URL，只剥空锚点
    """
    site_host = (site_host or "").lower().removeprefix("www.")

    def _repl(m):
        label, target = m.group(1), m.group(2)
        if not label:
            return ""  # 空锚点（Docusaurus 标题直接链接）→ 移除
        if site_host and site_host in _host_of(target):
            return label  # 站内 → 留文本
        return m.group(0)  # 外部 → 保留

    return _MD_LINK.sub(_repl, text)


# ---------- 内容验收 ----------

_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[A-Za-z]+")


def count_chinese_chars(text):
    return len(_CJK.findall(text))


def count_content_units(text):
    """内容量 = 中文字数 + 英文词数。语言政策：教材级源不限语言，
    英文权威源（WHO/arXiv）同样是有效素材，不得按中文字数误杀。"""
    return len(_CJK.findall(text)) + len(_LATIN_WORD.findall(text))


def is_valid_content(text, min_chars=500):
    """正文 ≥ min_chars 个内容单位（中文字+英文词）才算采到真内容（防导航页/空页）。"""
    return count_content_units(text) >= min_chars


# ---------- 验收门槛 ----------

def check_acceptance(total_chars, target_words, coverage):
    """素材验收：总量 ≥ 3×目标成稿字数；每个 TOP 问题 ≥2 独立来源。

    coverage: {问题: 已覆盖来源数}
    返回 {"material_ok": bool, "coverage_gaps": [...], "needed_chars": int}
    """
    needed = target_words * 3
    gaps = [q for q, n in coverage.items() if n < 2]
    return {
        "material_ok": total_chars >= needed,
        "coverage_gaps": gaps,
        "needed_chars": max(0, needed - total_chars),
        "达标线": needed,
    }


# ---------- 落盘 ----------

_BAD_FILENAME = re.compile(r'[\\/:*?"<>|？?！!，,。.\s]+')


def organize_path(output_dir, layer, title):
    """按层分目录落盘：<output_dir>/<layer>/<安全文件名>.md"""
    safe = _BAD_FILENAME.sub("_", title).strip("_")[:60] or "untitled"
    d = os.path.join(output_dir, layer)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, safe + ".md")


def manifest_entry(url, layer, title, path, words, channel, status, retries, covers):
    return {"url": url, "layer": layer, "title": title, "path": path,
            "字数": words, "channel": channel, "status": status,
            "重试次数": retries, "覆盖问题": covers}


def write_manifest(output_dir, entries, topic, target_words, total_chars,
                   coverage=None):
    """写 coverage-manifest.json：逐条记录 + 验收结论，可被下游原子技能读取。"""
    coverage = coverage or {}
    acc = check_acceptance(total_chars, target_words, coverage)
    data = {
        "topic": topic,
        "target_words": target_words,
        "总字数": total_chars,
        "entries": entries,
        "观察哨": [e["url"] for e in entries if e.get("value") == "unknown"],
        "验收": acc,
    }
    p = os.path.join(output_dir, "coverage-manifest.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="教程采集层工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("channel", help="决定 URL 走哪个采集通道")
    c.add_argument("--url", required=True)
    c.add_argument("--action", default="单页采集")
    c.add_argument("--no-firecrawl-key", action="store_true",
                   help="无 firecrawl key（download 降级为 scrape）")

    pp = sub.add_parser("postprocess", help="剥站内锚点链接噪音")
    pp.add_argument("--file", required=True)
    pp.add_argument("--site-host", default=None)

    v = sub.add_parser("validate", help="校验正文是否够料")
    v.add_argument("--file", required=True)
    v.add_argument("--min-chars", type=int, default=500)

    m = sub.add_parser("manifest", help="汇总输出 coverage-manifest.json")
    m.add_argument("--dir", required=True)
    m.add_argument("--topic", required=True)
    m.add_argument("--target-words", type=int, default=8000)

    x = sub.add_parser("explain", help="给失败/存疑文件定性（quota/blocked/thin/ok）")
    x.add_argument("--file", required=True)

    h = sub.add_parser("harvest-one", help="单条源全自动采集落盘（确定性通道）")
    h.add_argument("--dir", required=True)
    h.add_argument("--url", required=True)
    h.add_argument("--title", required=True)
    h.add_argument("--layer", default="L3")
    h.add_argument("--value", default="unknown")
    h.add_argument("--action", default="单页采集")

    args = ap.parse_args()

    if args.cmd == "channel":
        ch = pick_channel(args.url, args.action,
                          firecrawl_available=not args.no_firecrawl_key)
        print(json.dumps({"channel": ch}, ensure_ascii=False))
    elif args.cmd == "postprocess":
        text = open(args.file, encoding="utf-8").read()
        out = postprocess_markdown(text, site_host=args.site_host)
        open(args.file, "w", encoding="utf-8").write(out)
        print(json.dumps({"stripped_to": len(out)}, ensure_ascii=False))
    elif args.cmd == "validate":
        text = open(args.file, encoding="utf-8").read()
        n = count_chinese_chars(text)
        print(json.dumps({"chinese_chars": n, "valid": is_valid_content(text, args.min_chars)},
                         ensure_ascii=False))
    elif args.cmd == "manifest":
        # 扫输出目录既有 .md 汇总 manifest（Agent 采集完跑这个收口）
        entries, total = [], 0
        for root, _dirs, files in os.walk(args.dir):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(root, fn)
                text = open(p, encoding="utf-8").read()
                words = count_content_units(text)
                total += words
                entries.append(manifest_entry(
                    url="", layer=os.path.basename(root), title=fn[:-3],
                    path=os.path.relpath(p, args.dir), words=words,
                    channel="", status="ok", retries=0, covers=[]))
        write_manifest(args.dir, entries, args.topic, args.target_words, total)
        print(json.dumps({"total_chars": total, "files": len(entries)},
                         ensure_ascii=False))
    elif args.cmd == "explain":
        print(json.dumps(explain(args.file), ensure_ascii=False))
    elif args.cmd == "harvest-one":
        src = {"title": args.title, "url": args.url, "layer": args.layer,
               "value": args.value, "action": args.action}
        try:
            dest = harvest_one(args.dir, src)
            print(json.dumps({"dest": dest, "channel": pick_channel(args.url, args.action)}, ensure_ascii=False))
        except HarvestError as e:
            print(json.dumps({"error": e.category, "channel": e.channel, "advice": e.advice},
                             ensure_ascii=False))
            sys.exit(1)




# ---------- #1 排障纪律：validate 必须能解释失败原因（9/5 教训：误判烧配额） ----------

_EXPLAIN_RULES = [
    ("quota", re.compile(r"rate limit|free tier|配额", re.I),
     "firecrawl 配额耗尽：等重置（每小时整点）或配 ~/.config/gin-tutorial/config.yaml 的 firecrawl_api_key"),
    ("blocked", re.compile(r"do not support this site|403|not supported", re.I),
     "目标站/通道封禁：按降级阶梯换 opencli 或 collector，勿重试同一通道"),
    ("empty", None, "采集无输出：检查命令是否执行成功"),
]


def explain(path, min_chars=500):
    """给失败文件定性。返回 {"category", "units", "advice"}。

    category ∈ ok / quota / blocked / thin / empty——先定性再决定重试或降级，
    禁止不读输出就重试（9/5 配额误判成目标站封禁，白烧 3 轮重试的教训）。
    """
    if not os.path.exists(path):
        return {"category": "empty", "units": 0, "advice": "输出文件不存在，命令可能根本没跑成"}
    text = open(path, encoding="utf-8", errors="replace").read()
    head = text[:400]
    for cat, pat, advice in _EXPLAIN_RULES:
        if pat and pat.search(head):
            return {"category": cat, "units": count_content_units(text), "advice": advice}
    units = count_content_units(text)
    if units == 0:
        return {"category": "empty", "units": 0, "advice": "零内容：检查 URL 是否可达"}
    if units < 100:
        return {"category": "thin", "units": units,
                "advice": "真实页面但主内容稀薄（JS 渲染墙/导航页）：换 opencli 真实浏览器，勿同通道重试"}
    if units < min_chars:
        return {"category": "thin", "units": units,
                "advice": f"内容不足 {min_chars}：可能是节选页，可降门槛或换通道"}
    return {"category": "ok", "units": units, "advice": "内容有效"}


# ---------- #2 firecrawl key 管理（训记模式，与 source-scan 同约定） ----------

CONFIG_PATH = os.path.expanduser("~/.config/gin-tutorial/config.yaml")


def load_config():
    """读 key 配置。兼容两种形态：JSON 对象 或 用户直接粘贴的 key 纯文本。"""
    try:
        raw = open(CONFIG_PATH, encoding="utf-8").read().strip()
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        cfg = json.loads(raw)
        return cfg if isinstance(cfg, dict) else {}
    except ValueError:
        m = re.search(r"(fc-[A-Za-z0-9-]+)", raw)
        return {"firecrawl_api_key": m.group(1)} if m else {}


def firecrawl_env():
    """调 firecrawl-cli 前要注入的环境变量（有 key 才注入，keyless 什么都不加）。"""
    key = load_config().get("firecrawl_api_key")
    return {"FIRECRAWL_API_KEY": key} if key else {}


# ---------- #7/#8 harvest-one：单条源全自动（决策→采集→验收→后处理→落盘） ----------

def harvest_one(output_dir, src):
    """采集单条源并按层落盘。src: sources.json 条目（title/url/layer/value/action）。

    只负责确定性通道（firecrawl-scrape/download、collector、skip-book 的判定）；
    opencli 通道由 Agent 用 opencli-browser 技能执行（见 SKILL.md 责任表）。
    返回落盘路径；失败抛 HarvestError（带 explain 定性）。
    """
    url = src["url"]
    title, layer = src["title"], src.get("layer", "L3")
    if src.get("redundant_with"):
        raise HarvestError(url, "skip", "redundant",
                           f"冗余源（与已采 {src['redundant_with']} 同内容），不烧配额直接跳过")
    ch = pick_channel(url, src.get("action", "单页采集"),
                      firecrawl_available=bool(load_config().get("firecrawl_api_key")))
    if ch == "opencli":
        raise HarvestError(url, ch, "opencli", "opencli 通道由 Agent 执行（opencli-browser 技能），脚本不自动跑")
    if ch == "skip-book":
        raise HarvestError(url, ch, "skip-book", "书非采集对象，只记录书目")
    dest = organize_path(output_dir, layer, title)
    host = urlparse(url).netloc.lower().removeprefix("www.")
    raw = dest[:-3] + ".raw.md"

    env = dict(os.environ)
    env.update(firecrawl_env())
    scrape_url, via_note = url, ""
    cmd = ["npx", "-y", "firecrawl-cli", "scrape", scrape_url, "--only-main-content", "-o", raw]
    subprocess.run(cmd, capture_output=True, timeout=300, env=env)
    info = explain(raw)
    if info["category"] == "blocked":
        mirror = academic_mirror(url)
        if mirror["mirror"]:
            scrape_url = mirror["mirror"]
            via_note = mirror["note"]
            cmd = ["npx", "-y", "firecrawl-cli", "scrape", scrape_url,
                   "--only-main-content", "-o", raw]
            subprocess.run(cmd, capture_output=True, timeout=300, env=env)
            info = explain(raw)
    if info["category"] != "ok":
        advice = info["advice"]
        if via_note == "" and info["category"] == "blocked":
            advice += "；" + academic_mirror(url)["note"]
        raise HarvestError(url, ch, info["category"], advice)
    postprocess_markdown_inplace = postprocess_markdown(open(raw, encoding="utf-8").read(), site_host=host)
    header = (f"> 来源：{title}\n> URL：{url}\n> 层级：{layer} | 定级：{src.get('value', '?')}"
              f" | 通道：{ch}{('（' + via_note + '）') if via_note else ''}\n\n---\n\n")
    open(dest, "w", encoding="utf-8").write(header + postprocess_markdown_inplace)
    os.remove(raw)
    return dest


class HarvestError(Exception):
    def __init__(self, url, channel, category, advice):
        self.url, self.channel, self.category, self.advice = url, channel, category, advice
        super().__init__(f"[{category}] {url}: {advice}")


if __name__ == "__main__":
    main()


# ---------- #3 学术镜像降级（L6 结构性盲区，9/5 实测教训） ----------

_ACADEMIC_HOSTS = ("pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
                   "thelancet.com", "www.thelancet.com")


def academic_mirror(url):
    """L6 学术源被封时的镜像路由。返回 {"mirror": url|None, "note": str}。

    pubmed/pmc → Europe PMC 同 ID 镜像（firecrawl 友好，同全文）；
    thelancet 付费墙无可靠镜像 → 给 opencli/人工补采建议，不返回假 URL。
    """
    netloc = urlparse(url).netloc.lower()
    if netloc not in _ACADEMIC_HOSTS:
        return {"mirror": None, "note": ""}
    m = re.search(r"/(\d{6,9})/?", urlparse(url).path)
    if "pubmed" in netloc and m:
        return {"mirror": f"https://europepmc.org/article/MED/{m.group(1)}",
                "note": f"PubMed 经 Europe PMC 镜像补采（同 PMID {m.group(1)}）"}
    m = re.search(r"/(PMC\d+)/?", urlparse(url).path, re.I)
    if "pmc" in netloc and m:
        return {"mirror": f"https://europepmc.org/articles/{m.group(1)}",
                "note": f"PMC 经 Europe PMC 镜像补采（同 {m.group(1)}）"}
    return {"mirror": None,
            "note": "学术源封禁且无可靠镜像（Lancet 付费墙类）：opencli 浏览器补采或人工下载 PDF"}
