#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_source_grader.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import source_grader as sg


def test_gov_primary():
    assert sg.grade_url("http://www.nhc.gov.cn/xxx") == "primary"


def test_zhihu_tertiary():
    assert sg.grade_url("https://www.zhihu.com/question/123") == "tertiary"


def test_sohu_secondary():
    assert sg.grade_url("https://www.sohu.com/a/123") == "secondary"


def test_unknown():
    assert sg.grade_url("https://unknown-site.example.com") is None


if __name__ == "__main__":
    test_gov_primary()
    test_zhihu_tertiary()
    test_sohu_secondary()
    test_unknown()
    print("test_source_grader OK")
