#!/usr/bin/env python3
from pathlib import Path
import base64, re, subprocess, shutil
ROOT=Path(__file__).resolve().parent
items=[
 ("01-antv-chart/chart.svg", "#f7f3ea"),
 ("02-excalidraw/diagram.svg", "#fffdf8"),
 ("03-mermaid/sequence.svg", "#ffffff"),
 ("04-anatomy/anatomy.svg", "#f4eee2"),
]
for rel,bg in items:
    p=ROOT/rel
    svg=p.read_text(encoding="utf-8")
    m=re.search(r'width="(\d+)" height="(\d+)"',svg)
    w,h=int(m.group(1)),int(m.group(2))
    maxw=1480; scale=min(maxw/w,1480/h)
    iw,ih=w*scale,h*scale
    x=(1600-iw)/2; y=(1600-ih)/2
    b64=base64.b64encode(svg.encode()).decode()
    out=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1600" viewBox="0 0 1600 1600">
<rect width="1600" height="1600" fill="{bg}"/>
<image href="data:image/svg+xml;base64,{b64}" x="{x:.1f}" y="{y:.1f}" width="{iw:.1f}" height="{ih:.1f}"/>
</svg>'''
    (p.parent/"preview.svg").write_text(out,encoding="utf-8")
    # qlmanage
    png=p.parent/"preview.svg.png"
    if png.exists(): png.unlink()
    subprocess.run(["qlmanage","-t","-s","1600","-o",str(p.parent),str(p.parent/"preview.svg")],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    png.rename(p.parent/"preview.png")
    print("preview",p.parent/"preview.png")
