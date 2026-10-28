#!/usr/bin/env python3
from pathlib import Path
import base64, io, re
import markdown
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
MD=ROOT/'docs/书/Agent入门-试读版-2026-10-22.md'
OUT=ROOT/'docs/书/Agent入门-试读版-2026-10-22.html'

text=MD.read_text(encoding='utf-8')
body=markdown.markdown(text,extensions=['extra','tables','sane_lists','fenced_code'],output_format='html5')
# drop the duplicate book title under the cover
body=re.sub(r'<h1>Agent 入门.*?</h1>', '', body, count=1, flags=re.S)

# remove the plain in-body TOC; the sidebar is the navigation
body=re.sub(r'<h2>目录</h2>.*?(?=<h1)', '', body, flags=re.S)

# assign ids to h1 parts / h2 lectures and collect toc
headings=[]
def tag(m):
    level=int(m.group(1)); inner=m.group(2)
    idx=len(headings)+1
    ident=f'part-{idx}' if level==1 else f'sec-{idx}'
    headings.append((level, re.sub('<[^>]+>','',inner).strip(), ident))
    return f'<h{level} id="{ident}">{inner}</h{level}>'
body=re.sub(r'<h([12])>(.*?)</h\1>', tag, body, flags=re.S)

parts=[]
for level,title,ident in headings:
    if level==1:
        parts.append({'title':title,'id':ident,'items':[]})
    else:
        if not parts: parts.append({'title':'正文','id':'','items':[]})
        parts[-1]['items'].append((title,ident))

toc=['<div class="toc-title"><span>目录</span><button id="toc-close" aria-label="关闭目录">×</button></div>',
     '<div class="toc-sub">6 篇 · 32 讲 · 13 组图</div>']
for p in parts:
    if p['id']:
        toc.append(f'<a class="toc-part" href="#{p["id"]}">{p["title"]}</a>')
    else:
        toc.append(f'<div class="toc-part">{p["title"]}</div>')
    for title,ident in p['items']:
        toc.append(f'<a class="toc-link" href="#{ident}">{title}</a>')
toc_html='\n'.join(toc)

# embed images as data URIs
def embed(m):
    pre,src,post=m.group(1),m.group(2),m.group(3)
    if src.startswith(('data:','http')): return m.group(0)
    p=(OUT.parent/src).resolve()
    if not p.exists(): return m.group(0)
    im=Image.open(p).convert('RGB')
    if im.width>1400:
        im=im.resize((1400,round(im.height*1400/im.width)),Image.LANCZOS)
    buf=io.BytesIO(); im.save(buf,format='PNG',optimize=True)
    b64=base64.b64encode(buf.getvalue()).decode()
    return f'{pre}data:image/png;base64,{b64}{post}'
body=re.sub(r'(<img[^>]*?src=")([^"]+)("[^>]*>)', embed, body)

css='''
:root{--paper:#f7f2e8;--ink:#2f2b26;--muted:#7d7466;--line:#d8d0c2;--orange:#d95f24}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans SC",sans-serif;line-height:1.9}
.cover{min-height:78vh;display:flex;flex-direction:column;justify-content:center;padding:9vw 9vw 7vw;border-bottom:3px solid var(--ink);background:radial-gradient(circle at 84% 20%,#fff7e8,transparent 45%),var(--paper)}
.kicker{font-size:11px;letter-spacing:.26em;font-weight:900;color:var(--muted)}
.cover h1{font-family:"Songti SC","STSong","STHeiti",serif;font-size:clamp(44px,7vw,92px);line-height:1.02;margin:16px 0 14px;letter-spacing:-.03em}
.cover .lead{max-width:720px;font-size:16px;color:#5f5648}
.cover .meta{margin-top:34px;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);line-height:1.8}
.cover .rule{width:120px;height:4px;background:var(--orange);margin-top:26px}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);gap:38px;max-width:1340px;margin:0 auto;padding:42px 28px 100px}
.toc-side{position:sticky;top:18px;align-self:start;max-height:calc(100vh - 36px);overflow:auto;padding:14px 12px 18px;border:1px solid var(--line);border-radius:12px;background:rgba(255,253,248,.86);backdrop-filter:blur(6px);font-size:12px}
.toc-title{display:flex;justify-content:space-between;align-items:center;font-weight:900;letter-spacing:.12em;font-size:12px;padding:4px 6px 8px;border-bottom:1px dashed var(--line)}
#toc-close{display:none;border:0;background:none;font-size:20px;cursor:pointer;color:var(--muted)}
.toc-sub{font-size:10px;color:var(--muted);padding:7px 6px 10px}
.toc-part{display:block;font-size:10px;font-weight:900;letter-spacing:.12em;color:var(--muted);margin:12px 6px 4px;text-decoration:none}
.toc-link{display:block;padding:4px 6px 4px 12px;border-left:2px solid transparent;color:#5f574c;text-decoration:none;line-height:1.45;border-radius:0 4px 4px 0}
.toc-link:hover{background:#f3ecdd;color:var(--ink)}
.toc-link.active{border-left-color:var(--orange);background:#fff2df;color:var(--ink);font-weight:800}
.book{max-width:900px;padding:0;margin:0}
h1{font-family:"Songti SC","STSong","STHeiti",serif;font-size:42px;border-bottom:3px solid var(--ink);padding-bottom:14px;margin:72px 0 26px}
h2{font-family:"Songti SC","STSong","STHeiti",serif;font-size:33px;margin:64px 0 18px;padding-top:18px;border-top:1px solid var(--line);scroll-margin-top:18px}
h3{font-size:22px;margin:42px 0 12px;scroll-margin-top:18px}
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
.toc-fab{display:none;position:fixed;right:18px;bottom:18px;z-index:60;border:1px solid var(--ink);background:var(--ink);color:#fff;border-radius:999px;padding:10px 16px;font-weight:800;box-shadow:0 6px 18px rgba(0,0,0,.18);cursor:pointer}
.toc-scrim{display:none}
@media(max-width:900px){
  .layout{grid-template-columns:1fr;padding:28px 18px 90px}
  .book{max-width:none}
  .toc-fab{display:block}
  .toc-side{position:fixed;left:0;top:0;bottom:0;z-index:70;width:min(86vw,330px);max-height:none;border-radius:0;transform:translateX(-105%);transition:transform .22s ease;background:#fffdf8;box-shadow:0 0 40px rgba(0,0,0,.18)}
  .toc-side.open{transform:none}
  #toc-close{display:block}
  .toc-scrim.show{display:block;position:fixed;inset:0;background:rgba(0,0,0,.28);z-index:65}
  h1{font-size:34px}h2{font-size:27px}
  .cover{padding:12vw 7vw}
}
@media(min-width:901px){.toc-fab{display:none}}
'''
cover='''<header class="cover">
<div class="kicker">STRUCTURE / VISUAL TRIAL EDITION · 2026-10-22</div>
<h1>Agent 入门<br>结构 / 视觉试读版</h1>
<p class="lead">6 篇 32 讲。这一版统一了每讲的入口，重写了第 12 讲，并把书中全部插图统一成手绘卡片风格。</p>
<div class="rule"></div>
<div class="meta">6 篇 · 32 讲 · 13 组图<br>正文仍是初稿；第 12 讲为试读重写<br>第 4 / 26 / 32 讲待写</div>
</header>'''
js='''
const side=document.getElementById('toc');
const fab=document.getElementById('toc-fab');
const scrim=document.getElementById('toc-scrim');
const close=document.getElementById('toc-close');
function openToc(){side.classList.add('open');scrim.classList.add('show')}
function closeToc(){side.classList.remove('open');scrim.classList.remove('show')}
fab.addEventListener('click',openToc); close.addEventListener('click',closeToc); scrim.addEventListener('click',closeToc);
side.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{if(window.innerWidth<=900)closeToc()}));
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeToc()});
const links=[...document.querySelectorAll('.toc-link')];
const secs=links.map(a=>document.querySelector(a.getAttribute('href'))).filter(Boolean);
function active(){
  const y=window.scrollY+110; let cur=secs[0];
  for(const s of secs){if(s.offsetTop<=y)cur=s;else break}
  links.forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+cur.id));
}
window.addEventListener('scroll',active,{passive:true}); window.addEventListener('resize',active); active();
'''
html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Agent 入门 · 结构/视觉试读版</title><style>{css}</style></head><body>
{cover}
<button class="toc-fab" id="toc-fab" aria-label="打开目录">目录</button>
<div class="toc-scrim" id="toc-scrim"></div>
<div class="layout">
<aside class="toc-side" id="toc" aria-label="全书目录">{toc_html}</aside>
<main class="book" id="book">{body}</main>
</div>
<script>{js}</script>
</body></html>'''
OUT.write_text(html,encoding='utf-8')
print('written',OUT,'chars',len(html),'size MB',round(OUT.stat().st_size/1024/1024,2),'images',len(re.findall(r'<img',body)),'toc parts',len(parts))
