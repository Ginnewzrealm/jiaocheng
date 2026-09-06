#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-tutorial-harvest 通道调度、后处理、验收的 TDD 测试。

规则来源：9/2-9/3 减脂/力量训练实测记录——
- 站内锚点链接是纯噪音（Docusaurus 标题后挂 [](url "直接链接")，占文件 3/4 体积）
- 外部引用链接是溯源线索，必须保留
- 正文 <500 字判采集失败（抓到导航页/空页）
- 通道优先级：firecrawl scrape → opencli → collector；书不是采集对象
"""
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "harvest", Path(__file__).parent.parent / "scripts" / "harvest.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["harvest"] = mod
spec.loader.exec_module(mod)


# ---------- pick_channel：通道调度 ----------

def test_default_webpage_goes_firecrawl_scrape():
    assert mod.pick_channel("https://example.com/a", "单页采集", True) == "firecrawl-scrape"


def test_zhihu_goes_opencli():
    assert mod.pick_channel("https://www.zhihu.com/question/1", "单页采集", True) == "opencli"


def test_bilibili_column_goes_opencli():
    assert mod.pick_channel("https://www.bilibili.com/read/cv1", "opencli 真实浏览器通道", True) == "opencli"


def test_pdf_goes_collector():
    assert mod.pick_channel("https://example.org/a.pdf", "collector 采集", True) == "collector"


def test_book_action_is_skip():
    assert mod.pick_channel("https://book.douban.com/subject/1", "找电子版/购书", True) == "skip-book"


def test_whole_site_goes_download():
    assert mod.pick_channel("https://docs.example.com/", "整站扒取", True) == "firecrawl-download"


def test_zhihu_prefers_opencli_even_without_action_hint():
    """知乎 URL 即使 action 标错也应走 opencli——域名黑名单优先于 action 标注。"""
    assert mod.pick_channel("https://zhuanlan.zhihu.com/p/1", "单页采集", True) == "opencli"


# ---------- postprocess_markdown：后处理 ----------

DOCUSAURUS_NOISE = (
    "## 核心原则 [](https://docs.x.com/handbook/#核心原则 \"核心原则的直接链接\")\n"
    "能量守恒定律见 [WHO 指南](https://who.int/fact)。\n"
    "站内跳转 [下一节](https://docs.x.com/handbook/next)。\n"
)

def test_strip_empty_anchor_links_keep_text():
    """Docusaurus 标题锚点 [](url "title") → 剥掉链接只留显示文本（此处显示文本为空则整段移除）。"""
    out = mod.postprocess_markdown(DOCUSAURUS_NOISE, site_host="docs.x.com")
    assert "[](https://docs.x.com" not in out
    assert "## 核心原则" in out


def test_keep_external_reference_links():
    out = mod.postprocess_markdown(DOCUSAURUS_NOISE, site_host="docs.x.com")
    assert "[WHO 指南](https://who.int/fact)" in out


def test_strip_in_site_body_links_but_keep_display_text():
    """站内正文链接：剥掉 URL 但保留显示文本（阅读流不断）。"""
    out = mod.postprocess_markdown(DOCUSAURUS_NOISE, site_host="docs.x.com")
    assert "下一节" in out
    assert "https://docs.x.com/handbook/next" not in out


def test_postprocess_without_site_host_keeps_everything():
    """没有 site_host 信息时不乱删——只剥空锚点结构。"""
    out = mod.postprocess_markdown(DOCUSAURUS_NOISE, site_host=None)
    assert "https://who.int/fact" in out


# ---------- 内容验收 ----------

def test_short_content_is_invalid():
    assert mod.is_valid_content("太短了", min_chars=500) is False
    assert mod.is_valid_content("字" * 600, min_chars=500) is True


def test_count_chinese_chars():
    assert mod.count_chinese_chars("abc 力量训练 123") == 4


def test_english_source_counts_as_content():
    """语言政策：教材级源不限语言——英文 WHO 源不得按中文字数误杀（9/5 实测坑）。"""
    english = "physical activity " * 60  # 120 词，0 中文字
    assert mod.count_chinese_chars(english) == 0
    assert mod.is_valid_content(english, min_chars=100) is True


def test_content_units_mix_cjk_and_latin():
    assert mod.count_content_units("力量 training 计划 plan") == 6  # 4 中文字 + 2 英文词


# ---------- 验收门槛 ----------

def test_acceptance_material_volume():
    ok = mod.check_acceptance(total_chars=30000, target_words=8000, coverage={"a": 2, "b": 2})
    assert ok["material_ok"] is True
    bad = mod.check_acceptance(total_chars=10000, target_words=8000, coverage={"a": 2})
    assert bad["material_ok"] is False
    assert bad["needed_chars"] == 14000


def test_acceptance_coverage_min_two_sources():
    ok = mod.check_acceptance(total_chars=30000, target_words=8000, coverage={"a": 2, "b": 1})
    assert ok["coverage_gaps"] == ["b"]


# ---------- 落盘路径 ----------

def test_organize_path_layered_and_safe(tmp_path):
    p = mod.organize_path(str(tmp_path), "L1", "WHO 身体活动指南？")
    assert p.startswith(str(tmp_path))
    assert "L1" in p
    assert "？" not in Path(p).name
    assert Path(p).suffix == ".md"


# ---------- coverage manifest ----------

def test_manifest_entry_roundtrip(tmp_path):
    entries = [mod.manifest_entry(url="https://a.com", layer="L1", title="A",
                                  path="L1/A.md", words=5000, channel="firecrawl-scrape",
                                  status="ok", retries=1, covers=["减脂原理"])]
    p = mod.write_manifest(str(tmp_path), entries, topic="力量训练入门",
                           target_words=8000, total_chars=5000)
    import json
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    assert data["topic"] == "力量训练入门"
    assert data["entries"][0]["channel"] == "firecrawl-scrape"
    assert data["验收"]["material_ok"] is False  # 5000 < 24000


# ---------- #1 排障纪律：validate 必须能解释失败原因 ----------

def test_explain_classifies_rate_limit(tmp_path):
    f = tmp_path / "x.md"
    f.write_text('{"success":false,"error":"You\'ve hit Firecrawl\'s keyless free tier rate limit. To continue"}', encoding="utf-8")
    r = mod.explain(str(f))
    assert r["category"] == "quota"
    assert "配额" in r["advice"]

def test_explain_classifies_unsupported_site(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("We apologize but we do not support this site.", encoding="utf-8")
    assert mod.explain(str(f))["category"] == "blocked"

def test_explain_classifies_thin_render_wall(tmp_path):
    """真实页面但主内容稀薄（<100 单位）= JS 渲染墙，不是采集失败。"""
    f = tmp_path / "x.md"
    f.write_text("# 标题\n" + "导航栏菜单 " * 30, encoding="utf-8")
    r = mod.explain(str(f))
    assert r["category"] == "thin"

def test_explain_classifies_real_content(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("正文 " * 600, encoding="utf-8")
    assert mod.explain(str(f))["category"] == "ok"

def test_explain_missing_file(tmp_path):
    r = mod.explain(str(tmp_path / "nope.md"))
    assert r["category"] == "empty"


# ---------- #2 firecrawl key 管理（训记模式，与 source-scan 同约定） ----------

def test_load_config_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CONFIG_PATH", str(tmp_path / "nope.yaml"))
    assert mod.load_config() == {}

def test_load_config_reads_firecrawl_key(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(json.dumps({"firecrawl_api_key": "fc-test-123"}), encoding="utf-8")
    monkeypatch.setattr(mod, "CONFIG_PATH", str(cfg))
    env = mod.firecrawl_env()
    assert env["FIRECRAWL_API_KEY"] == "fc-test-123"

def test_load_config_no_key_returns_empty_env(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mod, "CONFIG_PATH", str(cfg))
    assert mod.firecrawl_env() == {}

def test_load_config_tolerates_plaintext_key(tmp_path, monkeypatch):
    """用户直接把 key 原文粘进文件（9/5 实测发生）也要能用。"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("fc-plaintext-abc\n", encoding="utf-8")
    monkeypatch.setattr(mod, "CONFIG_PATH", str(cfg))
    assert mod.load_config()["firecrawl_api_key"] == "fc-plaintext-abc"


# ---------- #7/#8 harvest-one：单条源全自动落盘 ----------

def test_harvest_one_full_pipeline(tmp_path, monkeypatch):
    """mock firecrawl 调用，验证 决策→落盘→验收 全链路 + 来源头。"""
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            stdout = '{"channel": "firecrawl-scrape"}' if "channel" in cmd else ""
            stderr = ""
        if "channel" in cmd:
            return R()
        if "firecrawl-cli" in " ".join(cmd):
            out = cmd[cmd.index("-o") + 1]
            open(out, "w", encoding="utf-8").write("真实正文内容 " * 200)
        return R()
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod, "CONFIG_PATH", str(tmp_path / "no-cfg.yaml"))
    src = {"title": "测试文章", "url": "https://example.com/a", "layer": "L3",
           "value": "medium", "action": "单页采集"}
    dest = mod.harvest_one(str(tmp_path), src)
    assert dest.endswith(".md")
    assert "L3" in dest
    text = open(dest, encoding="utf-8").read()
    assert "> 来源：测试文章" in text and "> URL：https://example.com/a" in text
    assert "真实正文内容" in text
    assert any("firecrawl-cli" in " ".join(c) and "--only-main-content" in c for c in calls)


# ---------- #3 学术镜像降级（L6 结构性盲区，9/5 实测：PubMed/PMC 挂在最脆弱通道上） ----------

def test_mirror_pubmed_to_europepmc():
    """PubMed 摘要页被封 → Europe PMC 同 PMID 镜像（同内容，firecrawl 友好）。"""
    r = mod.academic_mirror("https://pubmed.ncbi.nlm.nih.gov/37248144/")
    assert r["mirror"] == "https://europepmc.org/article/MED/37248144"

def test_mirror_pmc_article_to_europepmc():
    r = mod.academic_mirror("https://pmc.ncbi.nlm.nih.gov/articles/PMC11930668/")
    assert r["mirror"] == "https://europepmc.org/articles/PMC11930668"

def test_lancet_paywall_no_mirror_but_advice():
    """Lancet 付费墙没有可靠镜像：不返回假 URL，给 opencli/人工补采建议。"""
    r = mod.academic_mirror("https://www.thelancet.com/journals/eclinm/article/PIIS2589-5370(24)00098-1/fulltext")
    assert r["mirror"] is None
    assert "opencli" in r["note"] or "人工" in r["note"]

def test_non_academic_url_no_mirror():
    assert mod.academic_mirror("https://post.smzdm.com/p/az8qvv5n")["mirror"] is None

def test_mirror_id_extraction_edge_cases():
    """尾斜杠/多余路径都不应破坏 ID 提取。"""
    r = mod.academic_mirror("https://pubmed.ncbi.nlm.nih.gov/37248144/?format=pubmed")
    assert r["mirror"].endswith("/37248144")


# ---------- #4 冗余源：observe-only，不进重试队列 ----------

def test_harvest_one_skips_redundant_source(tmp_path):
    """sources.json 标了 redundant_with 的源：直接跳过，不烧采集配额。"""
    src = {"title": "人民日报健康短讯", "url": "https://m.peopledailyhealth.com/x",
           "layer": "L1", "value": "medium", "action": "单页采集",
           "redundant_with": "https://www.nhc.gov.cn/ylyjs/zcwj/202412/75cb79c171c94def9e768193e65484f7.shtml"}
    try:
        mod.harvest_one(str(tmp_path), src)
        raised = None
    except mod.HarvestError as e:
        raised = e
    assert raised is not None and raised.category == "redundant"
