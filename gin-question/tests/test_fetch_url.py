#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_fetch_url.py — fetch_url 诊断模式测试。"""

import json
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fetch_url


def test_fetch_http_success_returns_html():
    """HTTP 抓取成功应返回页面内容。"""
    html = "<html><h1>test</h1></html>"
    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock.Mock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_urlopen.return_value.__enter__ = mock.Mock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = mock.Mock(return_value=False)

        result = fetch_url.fetch_http("https://example.com")

    assert result == html


def test_fetch_http_failure_returns_error_dict():
    """HTTP 抓取失败应返回错误信息 dict。"""
    with mock.patch("urllib.request.urlopen", side_effect=Exception("403 Forbidden")):
        result = fetch_url.fetch_http("https://example.com")

    assert isinstance(result, dict)
    assert "403 Forbidden" in result["error"]
    assert result["method"] == "http"


def test_fetch_with_diagnostics_records_http_success():
    """fetch 带 diagnostics 时，HTTP 成功应记录诊断条目。"""
    html = "<html><h1>test</h1></html>"
    diag = fetch_url.FetchDiagnostics()

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock.Mock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_urlopen.return_value.__enter__ = mock.Mock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = mock.Mock(return_value=False)

        result = fetch_url.fetch("https://example.com", diagnostics=diag, use_opencli=False)

    assert result == html
    assert len(diag.entries) == 1
    entry = diag.entries[0]
    assert entry["url"] == "https://example.com"
    assert entry["method"] == "http"
    assert entry["success"] is True
    assert entry["content_length"] == len(html)
    assert "duration_ms" in entry


def test_fetch_with_diagnostics_records_http_failure_and_opencli_success():
    """HTTP 失败、OpenCLI 兜底成功时，应记录两条诊断条目。"""
    html = "<html><h1>from opencli</h1></html>"
    diag = fetch_url.FetchDiagnostics()

    with mock.patch("urllib.request.urlopen", side_effect=Exception("403 Forbidden")):
        with mock.patch("shutil.which", return_value="/usr/local/bin/opencli"):
            open_result = mock.Mock(returncode=0, stdout="", stderr="")
            extract_result = mock.Mock(returncode=0, stdout=html, stderr="")
            with mock.patch("subprocess.run", side_effect=[open_result, extract_result]) as mock_run:
                result = fetch_url.fetch("https://example.com", diagnostics=diag, use_opencli=True)

    assert result == html
    assert mock_run.call_count == 2
    assert len(diag.entries) == 2
    assert diag.entries[0]["method"] == "http"
    assert diag.entries[0]["success"] is False
    assert diag.entries[1]["method"] == "opencli"
    assert diag.entries[1]["success"] is True


def test_fetch_with_diagnostics_records_total_failure():
    """HTTP 和 OpenCLI 都失败时，应记录两条失败条目。"""
    diag = fetch_url.FetchDiagnostics()

    with mock.patch("urllib.request.urlopen", side_effect=Exception("403 Forbidden")):
        with mock.patch("shutil.which", return_value="/usr/local/bin/opencli"):
            open_result = mock.Mock(returncode=1, stdout="", stderr="timeout")
            with mock.patch("subprocess.run", side_effect=[open_result]) as mock_run:
                result = fetch_url.fetch("https://example.com", diagnostics=diag, use_opencli=True)

    assert isinstance(result, dict)
    assert mock_run.call_count == 1
    assert len(diag.entries) == 2
    assert diag.entries[0]["success"] is False
    assert diag.entries[1]["success"] is False
    assert "timeout" in diag.entries[1]["error"]


def test_run_diagnosis_outputs_report():
    """run_diagnosis 应输出 JSON 诊断报告。"""
    html = "<html><h1>test</h1></html>"
    urls = ["https://example.com/1", "https://example.com/2"]

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock.Mock()
        mock_response.read.return_value = html.encode("utf-8")
        mock_urlopen.return_value.__enter__ = mock.Mock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = mock.Mock(return_value=False)

        tmpdir = tempfile.mkdtemp()
        try:
            report_path = os.path.join(tmpdir, "fetch_diagnostics.json")
            fetch_url.run_diagnosis(urls, output_path=report_path, use_opencli=False)

            assert os.path.exists(report_path)
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            assert report["total_urls"] == 2
            assert report["success_count"] == 2
            assert report["failure_count"] == 0
            assert len(report["entries"]) == 2
        finally:
            import shutil
            shutil.rmtree(tmpdir)


def test_fetch_opens_strong_anti_crawl_domains_directly_with_opencli():
    """对强反爬域名应跳过 HTTP，直接调用 OpenCLI。"""
    html = "<html><h1>zhihu page</h1></html>"
    diag = fetch_url.FetchDiagnostics()

    with mock.patch("shutil.which", return_value="/usr/local/bin/opencli"):
        open_result = mock.Mock(returncode=0, stdout="", stderr="")
        extract_result = mock.Mock(returncode=0, stdout=html, stderr="")
        with mock.patch("subprocess.run", side_effect=[open_result, extract_result]) as mock_run:
            with mock.patch("urllib.request.urlopen") as mock_urlopen:
                # 如果 HTTP 被调用，测试失败
                mock_urlopen.side_effect = AssertionError("HTTP should not be called for zhihu.com")

                result = fetch_url.fetch("https://www.zhihu.com/question/123", diagnostics=diag, use_opencli=True)

    assert result == html
    assert mock_run.call_count == 2
    assert len(diag.entries) == 1  # 只有 opencli 一条记录
    assert diag.entries[0]["method"] == "opencli"
    assert diag.entries[0]["success"] is True


if __name__ == "__main__":
    test_fetch_http_success_returns_html()
    test_fetch_http_failure_returns_error_dict()
    test_fetch_with_diagnostics_records_http_success()
    test_fetch_with_diagnostics_records_http_failure_and_opencli_success()
    test_fetch_with_diagnostics_records_total_failure()
    test_run_diagnosis_outputs_report()
    test_fetch_opens_strong_anti_crawl_domains_directly_with_opencli()
    print("test_fetch_url OK")
