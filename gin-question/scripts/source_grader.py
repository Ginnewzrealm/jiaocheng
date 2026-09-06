#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""source_grader.py — 根据域名对来源进行一级/二级/三级分级。

规则来自 references/objective-rules.md 中的来源分级域名表。
"""

import re
from urllib.parse import urlparse


# 一手源域名模式
PRIMARY_PATTERNS = [
    r"^github\.com$",
    r"^.*\.official\.site$",
    r"^arxiv\.org$",
    r"^scholar\.google\.com$",
    r"^iso\.org$",
    r"^nist\.gov$",
    r"^(www\.)?.*\.gov$",
    r"^(www\.)?.*\.gov\.cn$",
    r"^(www\.)?.*\.edu$",
    r"^(www\.)?.*\.edu\.cn$",
    r"^pmc\.ncbi\.nlm\.nih\.gov$",
    r"^pubmed\.ncbi\.nlm\.nih\.gov$",
    r"^www\.ncbi\.nlm\.nih\.gov$",
]

# 二手源域名模式
SECONDARY_PATTERNS = [
    r"^36kr\.com$",
    r"^huxiu\.com$",
    r"^caixin\.com$",
    r"^ftchinese\.com$",
    r"^iresearch\.cn$",
    r"^questmobile\.com\.cn$",
    r"^zhuanlan\.zhihu\.com$",
    r"^substack\.com$",
    r"^dxy\.com$",
    r"^thepaper\.cn$",
    r"^cn-healthcare\.com$",
    r"^medsci\.cn$",
    r"^(www\.)?sohu\.com$",
    r"^(www\.)?163\.com$",
    r"^(www\.)?sina\.com\.cn$",
    r"^(www\.)?sina\.cn$",
    r"^(www\.)?qq\.com$",
    r"^(www\.)?ifeng\.com$",
]

# 三手源域名模式（问答/论坛/社交媒体）
TERTIARY_PATTERNS = [
    r"^(www\.)?reddit\.com$",
    r"^(www\.)?zhihu\.com$",
    r"^(www\.)?baidu\.com$",
    r"^tieba\.baidu\.com$",
    r"^(www\.)?quora\.com$",
    r"^(www\.)?twitter\.com$",
    r"^(www\.)?x\.com$",
    r"^(www\.)?weibo\.com$",
    r"^(www\.)?youtube\.com$",
    r"^mp\.weixin\.qq\.com$",
    r"^www\.verybeaut\.com$",
    r"^www\.chameiwang\.com$",
    r"^www\.3zhijk\.com$",
    r"^www\.xiaohe\.cn$",
    r"^health\.baidu\.com$",
    r"^jingyan\.baidu\.com$",
    r"^yuanli\.zaixianjisuan\.com$",
    r"^qubie\.zaixianjisuan\.com$",
    r"^fitness\.yxlady\.com$",
    r"^life\.yxlady\.com$",
    r"^www\.51topsci\.com$",
    r"^m\.cndzys\.com$",
    r"^m\.120ask\.com$",
    r"^m\.bohe\.cn$",
    r"^fitness\.39\.net$",
    r"^www\.jianshu\.com$",
    r"^www\.mingchatang\.com$",
    r"^post\.smzdm\.com$",
    r"^www\.myprotein\.cn$",
    r"^www\.chaojiyimei\.com$",
    r"^www\.fh21\.com\.cn$",
    r"^www\.qm120\.com$",
    r"^www\.yueqizhijia\.com$",
    r"^www\.lb-jy\.com$",
    r"^www\.shnzm\.com$",
    r"^slsshequ\.com$",
    r"^greenutss\.com$",
    r"^goku-japan\.com$",
    r"^www\.som1eagle\.com$",
    r"^www\.usana\.com$",
    r"^www\.jianshen8\.com$",
    r"^www\.eatingwell\.com$",
    r"^www\.issaonline\.com$",
    r"^hanshujisuan\.zaixianjisuan\.com$",
    r"^doc\.xuehai\.net$",
    r"^ricky\.tw$",
    r"^www\.calctdee\.com$",
    r"^tdeecalculator\.org$",
    r"^www\.kqmmm\.com$",
    r"^www\.huopinyuan\.cn$",
    r"^www\.huopinyuan\.com$",
    r"^qzmazda\.com$",
    r"^anquan\.com\.cn$",
    r"^baiqi\.makepolo\.com$",
    r"^www\.wanlibk\.com$",
    r"^www\.lipid\.org$",
    r"^members\.gymhub\.com\.au$",
    r"^www\.perffectdrs\.com$",
    r"^www\.chameiwang\.com$",
    r"^www\.ensoulclinic\.com$",
    r"^www\.cosmeticskinclinic\.com$",
    r"^feelsynergy\.com$",
    r"^www\.verybeaut\.com$",
    r"^weightoff\.com\.tw$",
    r"^stardreamclinic\.com$",
    r"^doctorfit\.com\.tw$",
    r"^www\.nutrola\.app$",
    r"^www\.dr-heichao\.com\.tw$",
    r"^miketnelson\.com$",
    r"^everlywell\.com$",
    r"^www\.verywellfit\.com$",
    r"^www\.thefitnessphantom\.com$",
    r"^krauselabs\.net$",
    r"^new-beauty\.hk$",
    r"^www\.womenshealthmag\.com$",
    r"^www\.ouh\.nhs\.uk$",
    r"^www\.faa\.gov$",
    r"^medicalxpress\.com$",
    r"^link\.springer\.com$",
    r"^www\.nhs\.uk$",
    r"^www\.tasteofhome\.com$",
    r"^www\.taste\.com\.au$",
    r"^epaper\.tyrbw\.com$",
]


def _match_domain(domain, patterns):
    for pat in patterns:
        if re.match(pat, domain, re.IGNORECASE):
            return True
    return False


def grade_url(url):
    """返回给定 URL 的来源级别。

    返回 "primary" | "secondary" | "tertiary" | None
    """
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return None

    if _match_domain(domain, PRIMARY_PATTERNS):
        return "primary"
    if _match_domain(domain, SECONDARY_PATTERNS):
        return "secondary"
    if _match_domain(domain, TERTIARY_PATTERNS):
        return "tertiary"
    return None


def grade_urls(urls):
    """批量分级 URL。"""
    return {url: grade_url(url) for url in urls}


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 source_grader.py <url> [url...]")
        sys.exit(1)
    for url in sys.argv[1:]:
        print(f"{url}\t{grade_url(url)}")


if __name__ == "__main__":
    main()
