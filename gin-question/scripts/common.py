#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gin-question 脚本公共工具。"""

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCES_DIR = os.path.join(REPO_ROOT, "references")


def now_iso():
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_schema():
    return load_json(os.path.join(REFERENCES_DIR, "output-schema.json"))


def normalize_text(text):
    """问题文本归一化：去首尾空格、统一问号、繁简不做处理（依赖外部库时可选）。"""
    text = text.strip()
    text = text.replace("?", "？")
    return text


def is_question_like(text):
    """基于 objective-rules.md 中的正则，初筛疑似疑问句。"""
    text = text.strip()
    if text.endswith("？") or text.endswith("?"):
        return True
    # 含疑问词
    pattern = re.compile(r".*?(吗|呢|么|怎么|什么|为什么|为何|多少|哪些|哪个|是不是|能不能|可不可以|如何|哪里|何时|谁).*?[？?]?$")
    return bool(pattern.match(text))


def get_domain(url):
    """提取 URL 的域名。"""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def read_reference(filename):
    path = os.path.join(REFERENCES_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def id_for_index(idx, prefix="P"):
    return f"{prefix}{idx:03d}"
