#!/usr/bin/env python3
from pathlib import Path
import markdown
ROOT=Path(__file__).resolve().parents[2]
md_path=ROOT/'docs/书/Agent入门-试读版-2026-10-22.md'
out=ROOT/'docs/书/Agent入门-试读版-2026-10-22.html'
text=md_path.read_text(encoding='utf-8')
html=markdown.markdown(text,extensions=['extra','tables','sane_lists','fenced_code'],output_format='html5')
css='''
:root{--paper:#f7f2e8;--paper2:#fffdf8;--ink:#2f2b26;--muted:#7d7466;--line:#d8d0c2;--orange:#d95f24}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC",sans-serif;line-height:1.9}
.cover{min-height:78vh;display:flex;flex-direction:column;justify-content:center;padding:9vw 9vw 7vw;border-bottom:3px solid var(--ink);background:radial-gradient(circle at 84% 20%,#fff7e8,transparent 45%),var(--paper)}
.kicker{font-size:11px;letter-spacing:.26em;font-weight:900;color:var(--muted)}
.cover h1{font-family:"Songti SC","STSong","STHeiti",serif;font-size:clamp(44px,7vw,92px);line-height:1.02;margin:16px 0 14px;letter-spacing:-.03em}
.cover .lead{max-width:720px;font-size:16px;color:#5f5648}
.cover .meta{margin-top:34px;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);line-height:1.8}
.cover .rule{width:120px;height:4px;background:var(--orange);margin-top:26px}
.book{max-width:980px;margin:0 auto;padding:56px 32px 100px}
h1{font-family:"Songti SC","STSong","STHeiti",serif;font-size:44px;border-bottom:3px solid var(--ink);padding-bottom:14px;margin:72px 0 26px}
h2{font-family:"Songti SC","STSong","STHeiti",serif;font-size:34px;margin:64px 0 18px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:22px;margin:42px 0 12px}
h4{font-size:17px;margin:28px 0 8px}
p{margin:10px 0}
a{color:#365f9e}
blockquote{margin:18px 0;padding:12px 18px;border-left:4px solid var(--orange);background:#fff8ea;color:#4f4638;border-radius:0 8px 8px 0}
blockquote p{margin:4px 0}
hr{border:0;border-top:1px dashed var(--line);margin:34px 0}
img{display:block;max-width:100%;height:auto;margin:22px auto;border:1px solid var(--line);border-radius:8px;box-shadow:0 8px 24px rgba(47,43,38,.08)}
table{border-collapse:collapse;width:100%;margin:18px 0;font-size:13px;background:#fffdf8}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#f1eadc;font-weight:800}
code{background:#f3ede2;padding:1px 4px;border-radius:4px;font-family:ui-monospace,Menlo,monospace;font-size:.92em}
pre{background:#27231f;color:#f6efe2;padding:16px;border-radius:8px;overflow:auto;font-size:12px;line-height:1.6}
pre code{background:none;color:inherit;padding:0}
ul,ol{padding-left:24px}
li{margin:4px 0}
@media(max-width:700px){.book{padding:36px 18px 70px}h1{font-size:34px}h2{font-size:27px}.cover{padding:12vw 7vw}}
'''
cover='''<header class="cover">
<div class="kicker">STRUCTURE / VISUAL TRIAL EDITION · 2026-10-22</div>
<h1>Agent 入门<br>结构 / 视觉试读版</h1>
<p class="lead">6 篇 32 讲。这一版统一了每讲的入口，重写了第 12 讲，并把书中 12 张图统一成手绘卡片风格。</p>
<div class="rule"></div>
<div class="meta">6 篇 · 32 讲 · 12 张图<br>正文仍是初稿；第 12 讲为试读重写<br>第 4 / 26 / 32 讲待写</div>
</header>'''
html=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Agent 入门 · 结构/视觉试读版</title><style>{css}</style></head><body>{cover}<main class="book">{html}</main></body></html>'
out.write_text(html,encoding='utf-8')
print('written',out,len(html),'chars')
