#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_url.py — 网页抓取：优先直接 HTTP，失败后尝试 OpenCLI，最后返回 None。

注意：本脚本不做问题提取，只负责获取网页原始 HTML/Markdown。
"""

import json
import shutil
import subprocess
import time
import urllib.request
from urllib.error import HTTPError, URLError


class FetchDiagnostics:
    """抓取诊断记录器。

    记录每次 URL 抓取的尝试、方法、结果、耗时和错误信息。
    不改变 fetch() 的返回行为，只用于事后分析。
    """

    def __init__(self):
        self.entries = []

    def record(self, url, method, success, content_length=0, error=None, duration_ms=0):
        self.entries.append({
            "url": url,
            "method": method,
            "success": success,
            "content_length": content_length,
            "error": error,
            "duration_ms": duration_ms,
        })

    def summary(self):
        total = len(self.entries)
        success = sum(1 for e in self.entries if e["success"])
        failure = total - success
        return {
            "total_urls": total,
            "success_count": success,
            "failure_count": failure,
            "entries": self.entries,
        }

    def save(self, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.summary(), f, ensure_ascii=False, indent=2)


# 已知强反爬域名列表：对这些域名跳过 HTTP，直接使用 OpenCLI
STRONG_ANTI_CRAWL_DOMAINS = [
    "zhihu.com",
    "baike.baidu.com",
]


def _is_strong_anti_crawl(url):
    """判断 URL 是否属于已知强反爬域名。"""
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(domain == d or domain.endswith("." + d) for d in STRONG_ANTI_CRAWL_DOMAINS)


def fetch_http(url, timeout=15, diagnostics=None):
    """使用 urllib 直接抓取网页。"""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        duration_ms = int((time.perf_counter() - start) * 1000)
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="http",
                success=True,
                content_length=len(content),
                duration_ms=duration_ms,
            )
        return content
    except (HTTPError, URLError, TimeoutError) as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="http",
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
        return {"error": str(e), "method": "http"}
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="http",
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
        return {"error": str(e), "method": "http"}


def fetch_opencli(url, timeout=60, diagnostics=None):
    """使用 OpenCLI browser 抓取网页。

    要求环境已安装 opencli 并配置好浏览器扩展。
    """
    start = time.perf_counter()
    if not shutil.which("opencli"):
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="opencli",
                success=False,
                error="opencli not installed",
            )
        return {"error": "opencli not installed", "method": "opencli"}
    try:
        session = "gin-question"
        # 1. 打开目标页面
        open_cmd = [
            "opencli", "browser", session, "open", url,
            "--window", "background",
        ]
        open_result = subprocess.run(open_cmd, capture_output=True, text=True, timeout=timeout)
        if open_result.returncode != 0:
            duration_ms = int((time.perf_counter() - start) * 1000)
            error = open_result.stderr or open_result.stdout or "opencli open failed"
            if diagnostics is not None:
                diagnostics.record(
                    url=url,
                    method="opencli",
                    success=False,
                    error=error,
                    duration_ms=duration_ms,
                )
            return {"error": error, "method": "opencli"}

        # 2. 提取页面内容为 markdown
        extract_cmd = [
            "opencli", "browser", session, "extract",
        ]
        extract_result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=timeout)
        duration_ms = int((time.perf_counter() - start) * 1000)
        if extract_result.returncode == 0:
            content = extract_result.stdout
            if diagnostics is not None:
                diagnostics.record(
                    url=url,
                    method="opencli",
                    success=True,
                    content_length=len(content),
                    duration_ms=duration_ms,
                )
            return content
        error = extract_result.stderr or extract_result.stdout or "opencli extract failed"
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="opencli",
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
        return {"error": error, "method": "opencli"}
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="opencli",
                success=False,
                error="opencli timeout",
                duration_ms=duration_ms,
            )
        return {"error": "opencli timeout", "method": "opencli"}
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if diagnostics is not None:
            diagnostics.record(
                url=url,
                method="opencli",
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
        return {"error": str(e), "method": "opencli"}


def fetch(url, use_opencli=True, diagnostics=None, opencli_timeout=60):
    """尝试多种方式抓取 URL。

    对已知强反爬域名跳过 HTTP，直接使用 OpenCLI。

    返回：
        - str: 成功时的网页内容
        - dict: 失败时的错误信息 {error, method}
    """
    # 对强反爬域名，直接走 OpenCLI
    if _is_strong_anti_crawl(url):
        if not use_opencli:
            return {"error": "strong anti-crawl domain and opencli disabled", "method": "skipped"}
        return fetch_opencli(url, timeout=opencli_timeout, diagnostics=diagnostics)

    # 1. 直接 HTTP
    result = fetch_http(url, diagnostics=diagnostics)
    if isinstance(result, str):
        return result

    # 2. OpenCLI 兜底
    if use_opencli:
        result2 = fetch_opencli(url, timeout=opencli_timeout, diagnostics=diagnostics)
        if isinstance(result2, str):
            return result2
        # 合并错误信息
        return {
            "error": f"http: {result.get('error')}; opencli: {result2.get('error')}",
            "method": "all_failed",
        }

    return result


def run_diagnosis(urls, output_path="fetch_diagnostics.json", use_opencli=True, delay_ms=0):
    """对一组 URL 运行抓取诊断并输出报告。

    urls: URL 列表，可以是字符串或 dict{"url": ..., "perspective": ..., "sub_dimension": ...}
    output_path: 诊断报告输出路径
    use_opencli: 是否启用 OpenCLI 兜底
    delay_ms: 请求间隔（毫秒），避免高频请求
    """
    diag = FetchDiagnostics()
    for item in urls:
        if isinstance(item, dict):
            url = item.get("url", "")
            meta = {k: v for k, v in item.items() if k != "url"}
        else:
            url = item
            meta = {}
        if not url:
            continue
        fetch(url, use_opencli=use_opencli, diagnostics=diag)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    report = diag.summary()
    report["config"] = {
        "use_opencli": use_opencli,
        "delay_ms": delay_ms,
    }
    diag.save(output_path)
    return report


def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 fetch_url.py <url> [--no-opencli] [--diagnose <urls.json> --output <report.json>]")
        sys.exit(1)

    if sys.argv[1] == "--diagnose":
        if len(sys.argv) < 3:
            print("--diagnose 需要指定 URL 列表 JSON 文件")
            sys.exit(1)
        urls_path = sys.argv[2]
        output_path = "fetch_diagnostics.json"
        use_opencli = "--no-opencli" not in sys.argv
        delay_ms = 0
        for i, arg in enumerate(sys.argv):
            if arg == "--output" and i + 1 < len(sys.argv):
                output_path = sys.argv[i + 1]
            if arg == "--delay-ms" and i + 1 < len(sys.argv):
                delay_ms = int(sys.argv[i + 1])

        with open(urls_path, "r", encoding="utf-8") as f:
            urls = json.load(f)
        report = run_diagnosis(urls, output_path=output_path, use_opencli=use_opencli, delay_ms=delay_ms)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    url = sys.argv[1]
    use_opencli = "--no-opencli" not in sys.argv
    out = fetch(url, use_opencli=use_opencli)
    if isinstance(out, str):
        print(out[:2000])  # 只打印前 2000 字符避免刷屏
    else:
        print(out)


if __name__ == "__main__":
    main()
