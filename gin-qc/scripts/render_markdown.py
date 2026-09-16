#!/usr/bin/env python3
"""Render the declared Markdown dialect and lint its actual block structure."""
import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from tutorial_contract import cli_error, diagnostic, finish, snapshots, stamp


def parser():
    try:
        from markdown_it import MarkdownIt
        from mdit_py_plugins.footnote import footnote_plugin
    except ImportError as exc:
        raise ValueError("缺 Markdown 解析器，请安装 gin-qc/requirements.txt") from exc
    return MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"]).use(footnote_plugin)


def tokenize(text):
    # Production markers are internal; keep blank lines so diagnostics retain positions.
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), text, flags=re.S)
    engine = parser()
    env = {}
    tokens = engine.parse(text, env)
    counts, anchors = {}, set()
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[i + 1]
        title = "".join(t.content for t in inline.children or [] if t.type in ("text", "code_inline"))
        slug = re.sub(r"[^\w\s-]", "", title.lower(), flags=re.U).strip().replace(" ", "-") or "section"
        index = counts.get(slug, 0)
        counts[slug] = index + 1
        anchor = slug if not index else f"{slug}-{index}"
        token.attrSet("id", anchor)
        anchors.add(anchor)
    for token in tokens:
        if token.type == "footnote_open":
            anchors.add(f"fn{token.meta['id'] + 1}")
    return engine, tokens, env, anchors


def cells(line):
    line = re.sub(r"`+[^`]*`+", "CODE", line.strip())
    return re.split(r"(?<!\\)\|", line.strip("|"))


def remote_state(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": "tutorial-link-check/3"}), timeout=8) as response:
            return "accessible", response.status
    except HTTPError as exc:
        return ("broken" if exc.code in (404, 410) else "restricted" if exc.code in (401, 403, 429) else "unknown"), exc.code
    except (URLError, TimeoutError, OSError):
        return "unknown", None


def lint(text, base_dir, check_remote=False):
    engine, tokens, env, anchors = tokenize(text)
    errors, warnings, dependencies, remotes = [], [], [], []
    lines = text.splitlines()
    levels = []
    urls = set()
    for token in tokens:
        if token.type == "heading_open":
            levels.append(int(token.tag[1:]))
        if token.type == "fence":
            start, end = token.map
            if not token.info.strip():
                errors.append(f"第 {start + 1} 行代码块缺语言标记")
            last = lines[end - 1].strip() if end <= len(lines) else ""
            last = re.sub(r"^(?:>\s*)+", "", last)
            if not re.fullmatch(re.escape(token.markup[0]) + "{" + str(len(token.markup)) + ",}\\s*", last):
                errors.append(f"第 {start + 1} 行代码围栏未闭合")
        if token.type == "table_open":
            start, end = token.map
            width = len(cells(lines[start]))
            for row in range(start + 2, end):
                if len(cells(lines[row])) != width:
                    errors.append(f"第 {row + 1} 行表格列数与表头不一致")
        for child in token.children or []:
            if child.type == "link_open":
                urls.add(child.attrGet("href"))
            if child.type == "image":
                urls.add(child.attrGet("src"))
                if not child.content.strip():
                    warnings.append("图片缺替代文本")
    if any(b - a > 1 for a, b in zip(levels, levels[1:])):
        errors.append("标题层级跳级")
    from tutorial_contract import prose
    clean = prose(text)
    refs = set(re.findall(r"\[\^([^\]]+)\](?!:)", clean))
    definitions = set(re.findall(r"^\[\^([^\]]+)\]:", clean, re.M))
    errors += [f"缺脚注定义：{r}" for r in sorted(refs - definitions)]
    for url in sorted(urls):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            state, code = remote_state(url) if check_remote else ("not_checked", None)
            remotes.append({"url": url, "status": state, "http_status": code})
            if state == "broken":
                errors.append(f"链接确定失效：{url}")
            elif state in ("restricted", "unknown"):
                warnings.append(f"链接需复核（{state}）：{url}")
            continue
        if parsed.scheme == "mailto":
            continue
        if parsed.scheme or parsed.netloc:
            warnings.append(f"未检查的链接协议：{url}")
            continue
        if parsed.path:
            target = (Path(base_dir) / unquote(parsed.path)).resolve()
            if not target.is_file():
                errors.append(f"本地资源不存在：{url}")
                continue
            dependencies.append(target)
            if parsed.fragment and target.suffix.lower() in (".md", ".markdown"):
                other = tokenize(target.read_text(encoding="utf-8"))[3]
                if unquote(parsed.fragment) not in other:
                    errors.append(f"跨文件锚点不存在：{url}")
        elif parsed.fragment and unquote(parsed.fragment) not in anchors:
            errors.append(f"目录锚点不存在：{url}")
    return diagnostic(errors, warnings, remote_links=remotes), dependencies, (engine, tokens, env)


CSS = """body{font:17px/1.75 system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 20px;color:#222}
pre{overflow-x:auto;padding:16px;background:#f4f5f6}code{font-family:ui-monospace,monospace}
img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow-x:auto}
td,th{border:1px solid #ddd;padding:8px 12px}blockquote{border-left:4px solid #aaa;margin-left:0;padding-left:16px}
a{overflow-wrap:anywhere}h1,h2,h3{line-height:1.35}@media(max-width:600px){body{margin:16px auto;font-size:16px}}
"""


def render_file(path, output, check_remote=False):
    path, output = Path(path).resolve(), Path(output).resolve()
    text = path.read_text(encoding="utf-8")
    result, dependencies, parsed = lint(text, path.parent, check_remote)
    engine, tokens, env = parsed
    # Rewrite only path-bearing local links. A <base> tag would break #anchors
    # and generated footnote links by resolving them against the source folder.
    for token in tokens:
        for child in token.children or []:
            attr = "href" if child.type == "link_open" else "src" if child.type == "image" else None
            if not attr:
                continue
            url = child.attrGet(attr)
            parsed_url = urlparse(url)
            if not parsed_url.scheme and not parsed_url.netloc and parsed_url.path:
                local = (path.parent / unquote(parsed_url.path)).resolve().as_uri()
                if parsed_url.query:
                    local += "?" + parsed_url.query
                if parsed_url.fragment:
                    local += "#" + parsed_url.fragment
                child.attrSet(attr, local)
    body = engine.renderer.render(tokens, engine.options, env)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(path.stem)}</title><style>{CSS}</style><body>{body}</body></html>', encoding="utf-8")
    result["preview"] = {"path": str(output), "sha256": snapshots([output])[0]["sha256"]}
    result["visual_review"] = "not_verified"
    return stamp(result, "render", [path, output] + dependencies, __file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--output")
    ap.add_argument("--check-remote", action="store_true")
    args = ap.parse_args()
    return finish(render_file(args.file, args.html, args.check_remote), args.output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        sys.exit(cli_error(exc))
