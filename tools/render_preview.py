#!/usr/bin/env python3
"""Render README.md / README.tr.md into GitHub-flavoured HTML for visual QA."""

import pathlib

import markdown

REPO = pathlib.Path("/opt/data/cache/scratch/challenge_repo")

GH_CSS = """
:root{--fg:#1f2328;--muted:#59636e;--border:#d1d9e0;--bg:#ffffff;--canvas:#f6f8fa;--link:#0969da}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1012px;margin:0 auto;padding:32px 32px 96px}
.markdown-body h1,.markdown-body h2{font-weight:600;letter-spacing:-.01em;padding-bottom:.3em;border-bottom:1px solid var(--border)}
.markdown-body h1{font-size:2em;margin:.67em 0}
.markdown-body h2{font-size:1.5em;margin-top:24px;margin-bottom:16px}
.markdown-body h3{font-size:1.25em;margin-top:24px;margin-bottom:16px;font-weight:600}
.markdown-body p{margin:0 0 16px}
.markdown-body a{color:var(--link);text-decoration:none}
.markdown-body a:hover{text-decoration:underline}
.markdown-body img[alt]{max-width:100%}
.markdown-body p>img{vertical-align:middle}
.markdown-body table{border-collapse:collapse;display:block;width:max-content;max-width:100%;overflow:auto;margin:0 0 16px;font-size:14px}
.markdown-body table th,.markdown-body table td{border:1px solid var(--border);padding:6px 13px}
.markdown-body table th{background:var(--canvas);font-weight:600;text-align:left}
.markdown-body table tr:nth-child(2n){background:#f6f8fa}
.markdown-body code{background:rgba(129,139,152,.12);padding:.2em .4em;border-radius:6px;font-size:85%;
  font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace}
.markdown-body pre{background:var(--canvas);padding:16px;overflow:auto;border-radius:6px;font-size:85%;line-height:1.45}
.markdown-body pre code{background:none;padding:0;font-size:100%}
.markdown-body blockquote{margin:0 0 16px;padding:0 1em;color:var(--muted);border-left:.25em solid var(--border)}
.markdown-body hr{height:.25em;padding:0;margin:24px 0;background:var(--border);border:0}
.markdown-body ol,.markdown-body ul{padding-left:2em;margin:0 0 16px}
.markdown-body li{margin:.25em 0}
.markdown-body [align=center]{text-align:center}
"""


def render(md_name: str, out_name: str):
    text = (REPO / md_name).read_text()
    html = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "attr_list", "md_in_html", "sane_lists"],
    )
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>{md_name}</title><style>{GH_CSS}</style></head>
<body><div class="wrap"><article class="markdown-body">{html}</article></div></body></html>"""
    p = REPO / out_name
    p.write_text(page)
    print(out_name, len(page), "bytes")


render("README.md", "_preview_en.html")
render("README.tr.md", "_preview_tr.html")
