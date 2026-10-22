#!/usr/bin/env python3
from pathlib import Path
import html, math, random

ROOT = Path(__file__).resolve().parent
FONT = "'PingFang SC','STHeiti','Heiti SC','Arial Unicode MS',sans-serif"
HAND = "'Chalkboard SE','Chalkboard','STHeiti',sans-serif"
MONO = "'SF Mono','Menlo','Courier New',monospace"

def e(s): return html.escape(str(s))
def txt(x,y,s,size=14,fill="#2f2b26",weight=400,anchor="start",family=FONT,opacity=1,spacing=None,extra=""):
    sp = f' letter-spacing="{spacing}"' if spacing else ''
    return f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" opacity="{opacity}"{sp} {extra}>{e(s)}</text>'
def rect(x,y,w,h,fill,stroke="none",sw=1,rx=0,opacity=1,extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}" {extra}/>'
def line(x1,y1,x2,y2,stroke="#2f2b26",sw=1,opacity=1,dash=None,extra=""):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{d} {extra}/>'
def circle(cx,cy,r,fill,stroke="none",sw=1,opacity=1,extra=""):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}" {extra}/>'
def path(d,fill="none",stroke="#2f2b26",sw=2,opacity=1,dash=None,extra=""):
    dd=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{dd} {extra}/>'
def svg(w,h,body,bg="#f7f3ea"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="8"/></filter>
  <filter id="rough" x="-10%" y="-10%" width="120%" height="120%">
    <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="7" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="2.2"/>
  </filter>
  <filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#2f2b26"/></marker>
  <marker id="arrow-blue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#4f7fd6"/></marker>
  <marker id="arrow-green" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#4e9a6a"/></marker>
</defs>
<rect width="{w}" height="{h}" fill="{bg}"/>
{body}
</svg>'''
def dots(w,h,step=26,color="#2f2b26",op=0.055):
    return ''.join(circle(x,y,1.2,color,opacity=op) for y in range(step,w,step) for x in range(step,h,step))

# ---------------- 01 ANT V CHART ----------------
def chart():
    W,H=1200,800
    body=[dots(W,H,28)]
    body.append(txt(70,62,"ANTV · CHART VISUALIZATION SKILL",11,"#8a7f6e",800,spacing="2.4"))
    body.append(txt(70,112,"一次开发任务的成本结构",36,"#2f2b26",800))
    body.append(txt(70,144,"3 次 LLM · 20 个事件 · 4,596 tokens",15,"#6f675c"))
    body.append(rect(945,58,190,32,"#fff","#d8d0c2",1,16))
    body.append(circle(962,74,4,"#5b8ff9"))
    body.append(txt(974,78,"G2 / G6 STYLE",10.5,"#4b453c",800,spacing="1.2"))

    # legend
    body.append(circle(196,198,5,"#5b8ff9")); body.append(txt(208,203,"Prompt tokens",11.5,"#5f574c"))
    body.append(circle(336,198,5,"#f6bd16")); body.append(txt(348,203,"Completion tokens",11.5,"#5f574c"))
    body.append(txt(700,203,"按 step 拆分",11.5,"#8a7f6e",anchor="end"))

    x0, y0, cw = 190, 228, 600
    maxv=2000
    for tick in range(0,2001,500):
        x=x0+cw*tick/maxv
        body.append(line(x,228,x,610,"#d8d0c2",1,0.75))
        body.append(txt(x,632,f"{tick:,}",10.5,"#8a7f6e",anchor="middle"))
    body.append(line(x0,610,x0+cw,610,"#b9ae9e",1.4))

    rows=[
        ("STEP 1","读 CSV + 写脚本",594,726,1320,"#5b8ff9","#f6bd16"),
        ("STEP 2","运行脚本",1374,42,1416,"#5b8ff9","#f6bd16"),
        ("STEP 3","总结回答",1560,300,1860,"#5b8ff9","#f6bd16"),
    ]
    ys=[270,390,510]
    for (lab,sub,p,c,total,c1,c2),y in zip(rows,ys):
        body.append(txt(70,y+4,lab,12,"#2f2b26",900,spacing="1.4"))
        body.append(txt(70,y+24,sub,10.5,"#8a7f6e"))
        wp=cw*p/maxv; wc=cw*c/maxv
        body.append(rect(x0,y,wp,42,c1,"none",0,6))
        body.append(rect(x0+wp,y,wc,42,c2,"none",0,6))
        body.append(txt(x0+wp-10,y+27,f"{p:,}",10.5,"#fff",700,anchor="end"))
        if wc > 34:
            body.append(txt(x0+wp+wc-10,y+27,f"{c:,}",10.5,"#5a4410",700,anchor="end"))
        else:
            body.append(txt(x0+wp+wc+4,y-6,f"{c:,}",9.5,"#8a6b1f",700))
        body.append(txt(x0+wp+wc+12,y+27,f"{total:,}",12,"#2f2b26",800))

    # right KPI panel
    px,py,pw,ph=850,228,280,382
    body.append(rect(px,py,pw,ph,"#fff","#e0d8ca",1,16))
    body.append(txt(px+22,py+28,"TOTAL TOKENS",10,"#8a7f6e",800,spacing="1.8"))
    body.append(txt(px+22,py+78,"4,596",44,"#2f2b26",800))
    body.append(txt(px+22,py+100,"prompt 3,528 · completion 1,068",10.5,"#8a7f6e"))
    # donut
    cx,cy,r=px+76,py+188,52
    C=2*math.pi*r
    frac=3528/4596
    body.append(circle(cx,cy,r,"none","#efe8da",14))
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#5b8ff9" stroke-width="14" stroke-dasharray="{C*frac:.2f} {C:.2f}" transform="rotate(-90 {cx} {cy})" stroke-linecap="round"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#f6bd16" stroke-width="14" stroke-dasharray="{C*(1-frac):.2f} {C:.2f}" stroke-dashoffset="{-C*frac:.2f}" transform="rotate(-90 {cx} {cy})" stroke-linecap="round"/>')
    body.append(txt(cx,cy+4,"77%",20,"#2f2b26",800,anchor="middle"))
    body.append(txt(cx,cy+22,"prompt",9.5,"#8a7f6e",anchor="middle"))
    body.append(circle(px+152,py+166,5,"#5b8ff9")); body.append(txt(px+164,py+170,"Prompt",10.5,"#5f574c"))
    body.append(txt(px+252,py+170,"3,528",10.5,"#2f2b26",700,anchor="end"))
    body.append(circle(px+152,py+194,5,"#f6bd16")); body.append(txt(px+164,py+198,"Compl.",10.5,"#5f574c"))
    body.append(txt(px+252,py+198,"1,068",10.5,"#2f2b26",700,anchor="end"))
    # stat chips
    chips=[("3","LLM CALLS"),("3","TOOL CALLS"),("20","EVENTS")]
    for i,(n,l) in enumerate(chips):
        yy=py+252+i*38
        body.append(rect(px+22,yy,236,30,"#faf7f0","#ece4d5",1,7))
        body.append(txt(px+36,yy+21,n,15,"#2f2b26",800))
        body.append(txt(px+236,yy+20,l,9.5,"#8a7f6e",800,anchor="end",spacing="1.2"))

    # insight
    body.append(rect(70,660,1060,78,"#fff8e8","#ead8aa",1,10))
    body.append(circle(94,699,5,"#d98a2b"))
    body.append(txt(108,688,"读图提示",11,"#8a6b1f",800,spacing="1.4"))
    body.append(txt(108,711,"Step 2 的 prompt 从 594 涨到 1,374：工具结果回填后，history 变长，这是 Agent 成本结构里最容易被忽略的一段。",12.5,"#5f4b25"))
    body.append(txt(70,782,"source: visualizer/trace_dev.jsonl  ·  skill: antvis/chart-visualization-skills  ·  rendered as SVG",9.5,"#9a9082"))
    return svg(W,H,''.join(body))

# ---------------- 02 EXCALIDRAW ----------------
def hand_rect(x,y,w,h,fill,stroke="#2f2b26",sw=2.4,rx=14):
    return f'<g filter="url(#rough)">{rect(x,y,w,h,fill,stroke,sw,rx)}</g>'
def hand_arrow(x1,y1,x2,y2,color="#2f2b26",dash=None,marker="arrow",sw=2.2):
    mx=(x1+x2)/2; my=(y1+y2)/2
    d=f"M {x1} {y1} C {x1+40} {y1-10} {x2-40} {y2+10} {x2} {y2}"
    return path(d,"none",color,sw,1,dash,f'marker-end="url(#{marker})" stroke-linecap="round"')

def excalidraw():
    W,H=1200,900
    body=[dots(W,H,28)]
    body.append(txt(56,64,"EXCALIDRAW · DIAGRAM SKILL",11,"#8a7f6e",800,spacing="2.2"))
    body.append(txt(56,112,"Agent Loop / 结构图",34,"#2f2b26",700,family=HAND))
    body.append(txt(56,140,"不是卡片墙：每个形状都在表达一种关系。",14,"#6f675c",family=HAND))
    body.append(rect(924,58,216,32,"#fff","#d8d0c2",1,16))
    body.append(txt(1032,79,"hand-drawn · SVG",10.5,"#4b453c",700,anchor="middle"))

    # guard note
    body.append(hand_rect(62,610,250,94,"#fff4d8","#d98a2b",2.2,12))
    body.append(txt(82,640,"GUARD",10,"#8a6b1f",900,spacing="1.6"))
    body.append(txt(82,666,"剩 2 步 · 预算预警",13,"#5f4b25",700,family=HAND))
    body.append(txt(82,688,"max_steps=3 · 先收尾",10.5,"#8a6b1f",family=HAND))

    # tools
    body.append(hand_rect(86,210,250,190,"#ffe8cc","#d98a2b",2.4,14))
    body.append(txt(108,240,"TOOLS",10,"#8a5b1e",900,spacing="1.8"))
    body.append(txt(108,272,"本地工具",20,"#2f2b26",800,family=HAND))
    chips=[("read_file","CSV"),("write_file","stats_tool.py"),("run_python","exit 0")]
    for i,(n,s) in enumerate(chips):
        y=292+i*32
        body.append(rect(108,y,206,25,"#fffaf2","#e2bd8a",1,7))
        body.append(txt(118,y+17,n,10.5,"#5f4b25",700,family=MONO))
        body.append(txt(306,y+17,s,9.5,"#8a6b1f",anchor="end",family=MONO))

    # hub
    body.append(hand_rect(438,188,324,158,"#2f2b26","#2f2b26",2.4,16))
    body.append(txt(462,220,"LLM + CONTEXT",10,"#b9b0a0",900,spacing="1.8"))
    body.append(txt(462,256,"一次运行的中枢",22,"#fff",800,family=HAND))
    body.append(txt(462,282,"deepseek-flash · ~98 tok",11,"#cfc7b8",family=MONO))
    body.append(rect(462,300,272,26,"#403b34","#5a544a",1,7))
    body.append(txt(474,317,"context window / tools schema",9.5,"#e8e1d5",family=MONO))

    # memory
    body.append(hand_rect(862,196,252,204,"#dff0e5","#4e9a6a",2.4,14))
    body.append(txt(884,226,"MEMORY",10,"#3f6b4f",900,spacing="1.8"))
    body.append(txt(884,258,"召回 1 条",20,"#2f2b26",800,family=HAND))
    body.append(rect(884,276,208,30,"#f7fcf8","#b9d8c4",1,6))
    body.append(txt(894,296,"用户偏好：JSON 输出",9.8,"#3f6b4f",family=HAND))
    body.append(txt(884,334,"写入：Extractor 待命",10.5,"#6f8a77",family=HAND))
    body.append(txt(884,356,"Chroma · embedding-v4",9.5,"#6f8a77",family=MONO))
    body.append(txt(884,378,"0.597",18,"#2f2b26",800,family=MONO))

    # answer
    body.append(hand_rect(438,606,324,104,"#e4edff","#4f7fd6",2.4,14))
    body.append(txt(460,634,"ANSWER",10,"#3f5377",900,spacing="1.8"))
    body.append(txt(460,662,"真实 stdout → 回答",18,"#2f2b26",800,family=HAND))
    body.append(txt(460,684,"A/B/C count / sum / avg",10.5,"#5f6f8a",family=MONO))

    # extractor
    body.append(hand_rect(842,606,272,104,"#f3e8ff","#8b5fb5",2.4,14))
    body.append(txt(864,634,"EXTRACTOR",10,"#6b438a",900,spacing="1.8"))
    body.append(txt(864,662,"keep / tags",19,"#2f2b26",800,family=HAND))
    body.append(txt(864,684,"这次待命",10.5,"#7f6694",family=HAND))

    # arrows
    body.append(hand_arrow(338,252,436,252,"#8a5b1e",None,"arrow",2.2))
    body.append(txt(356,242,"call",9.5,"#8a5b1e",700))
    body.append(hand_arrow(436,294,338,294,"#8a5b1e",None,"arrow",2.2))
    body.append(txt(356,312,"result",9.5,"#8a5b1e",700))
    body.append(hand_arrow(860,290,764,290,"#3f6b4f",None,"arrow-green",2.2))
    body.append(txt(792,278,"recall",9.5,"#3f6b4f",700))
    body.append(hand_arrow(600,348,600,600,"#4f7fd6",None,"arrow-blue",2.2))
    body.append(txt(612,480,"answer",9.5,"#4f7fd6",700))
    body.append(hand_arrow(764,658,840,658,"#6b438a",None,"arrow",2.2))
    body.append(txt(790,646,"write",9.5,"#6b438a",700))
    body.append(hand_arrow(978,604,978,404,"#4e9a6a",None,"arrow-green",2.2))
    body.append(txt(990,500,"store",9.5,"#3f6b4f",700))

    # dashed guard link
    body.append(hand_arrow(312,656,430,700,"#d98a2b","6 7","arrow",1.6))
    body.append(txt(330,724,"提醒收尾",9.5,"#8a6b1f",700))

    body.append(txt(56,858,"source: coleam00/excalidraw-diagram-skill  ·  structure view, not time view  ·  SVG",9.5,"#9a9082"))
    return svg(W,H,''.join(body),"#fffdf8")

# ---------------- 03 MERMAID ----------------
def mermaid():
    W,H=1200,900
    body=[]
    body.append(rect(0,0,W,H,"#ffffff"))
    body.append(txt(46,44,"MERMAID · SEQUENCE",11,"#7a6f60",800,spacing="2.2"))
    body.append(txt(46,80,"开发任务 · 消息时序",28,"#333",800,family="'Trebuchet MS','STHeiti',sans-serif"))
    body.append(txt(46,104,"source: sequence.mmd  ·  rendered in Mermaid style",10.5,"#888"))
    parts=[("User",120,"#ECECFF","#9370DB"),("LLM + Context",360,"#E8F4FF","#5B8FF9"),("Tools",610,"#FFF3E0","#E8A23A"),("Memory",850,"#E8F7EE","#5AD8A6"),("Extractor",1075,"#F5EAFE","#B37FEB")]
    bounds={}
    for name,x,fill,stroke in parts:
        w=185 if name=="LLM + Context" else 150
        body.append(rect(x-w/2,136,w,44,fill,stroke,1.2,5))
        body.append(txt(x,163,name,12.5,"#333",700,anchor="middle",family="'Trebuchet MS','STHeiti',sans-serif"))
        bounds[name]=x
        body.append(line(x,180,x,820,"#999",1,0.8,"4 5"))
    # activation
    body.append(rect(bounds["LLM + Context"]-7,198,14,540,"#E8F4FF","#5B8FF9",1,2,0.7))
    msgs=[
        ("User","LLM + Context","task",230,True),
        ("Memory","LLM + Context","recall 1 · JSON preference",290,False),
        ("LLM + Context","Tools","read_file(sales.csv)",350,True),
        ("Tools","LLM + Context","CSV 6 行",410,False),
        ("LLM + Context","Tools","write_file(stats_tool.py)",470,True),
        ("Tools","LLM + Context","wrote 2130 chars",530,False),
        ("LLM + Context","Tools","run_python(stats_tool.py)",590,True),
        ("Tools","LLM + Context","exit 0 · JSON stdout",650,False),
        ("LLM + Context","User","answer",710,False),
    ]
    for i,(a,b,label,y,solid) in enumerate(msgs,1):
        x1,x2=bounds[a],bounds[b]
        dash=None if solid else "6 5"
        color="#333" if solid else "#666"
        body.append(path(f"M {x1} {y} C {x1+(x2-x1)*.35} {y-10} {x2-(x2-x1)*.35} {y-10} {x2} {y}","none",color,1.5,1,dash,'marker-end="url(#arrow)"'))
        body.append(circle(x1,y,3.5,"#fff",color,1.2))
        body.append(txt((x1+x2)/2,y-10,label,10.5,"#333",600,anchor="middle",family="'Trebuchet MS','STHeiti',sans-serif"))
        body.append(circle(24,y-4,8,"#f3f0ff","#9370DB",1))
        body.append(txt(24,y,str(i),8,"#6b4fa0",700,anchor="middle",family=MONO))
    # note
    body.append(rect(bounds["Extractor"]-94,756,188,38,"#FFF8E1","#E8CA8A",1,5))
    body.append(txt(bounds["Extractor"],780,"Extractor · 待命（本次无写入）",9.5,"#7b5a1c",600,anchor="middle",family="'Trebuchet MS','STHeiti',sans-serif"))
    body.append(txt(46,858,"5 lifelines · 9 messages · solid = request · dashed = response",9.5,"#999"))
    return svg(W,H,''.join(body),"#ffffff")

# ---------------- 04 ANATOMY ----------------
def anatomy():
    W,H=1400,1000
    cx,cy,s=700,620,100
    def iso(x,y,z):
        return (cx+(x-y)*0.866*s, cy+(x+y)*0.5*s-z*s)
    def pts(points): return " ".join(f"{x:.1f},{y:.1f}" for x,y in points)
    def face(points,fill,stroke="#2b2722",sw=1.2,op=1):
        return f'<polygon points="{pts(points)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>'
    def box(x,y,z,sx,sy,sz,top,left,right,stroke="#2b2722",sw=1.2):
        p=[iso(x+i,y+j,z+k) for i,j,k in [(0,0,0),(sx,0,0),(sx,sy,0),(0,sy,0)]]
        pt=[iso(x+i,y+j,z+sz) for i,j,k in [(0,0,0),(sx,0,0),(sx,sy,0),(0,sy,0)]]
        out=[]
        out.append(face([pt[0],pt[1],pt[2],pt[3]],top,stroke,sw))
        # visible front-left / front-right faces
        out.append(face([p[3],p[2],pt[2],pt[3]],left,stroke,sw))
        out.append(face([p[2],p[1],pt[1],pt[2]],right,stroke,sw))
        return ''.join(out)
    def shadow(x,y,w,h,op=.16):
        return f'<ellipse cx="{x}" cy="{y}" rx="{w}" ry="{h}" fill="#2b2722" opacity="{op}" filter="url(#soft)"/>'

    body=[f'<rect width="{W}" height="{H}" fill="#f4eee2"/>']
    for gx in range(0,W,40): body.append(line(gx,0,gx,H,"#d9cfbd",1,0.2))
    for gy in range(0,H,40): body.append(line(0,gy,W,gy,"#d9cfbd",1,0.2))
    body.append(txt(56,62,"ANATOMY · ISOMETRIC SYSTEM FIGURE",11,"#7a6f60",800,spacing="2.4"))
    body.append(txt(56,112,"Agent 数据流引擎",40,"#221f1b",800,family="'Songti SC','STSong','STHeiti',serif"))
    body.append(txt(56,142,"把一次 Agent 运行拆成 6 个可触摸的部件。",14,"#6f6557"))
    body.append(txt(1280,62,"FIG. 01",12,"#7a6f60",800,anchor="end",spacing="2"))
    body.append(txt(1280,84,"SVG + WebGL-ready",10,"#9a8f7f",anchor="end",family=MONO))

    # base
    body.append(shadow(700,790,390,92,.14))
    body.append(box(-3.55,-2.45,0,7.1,4.9,.22,"#d9cdbb","#b7a994","#c8bba6"))
    for i in range(-3,4):
        a=iso(i,-2.45,.23); b=iso(i,2.45,.23)
        body.append(line(a[0],a[1],b[0],b[1],"#a99b86",1,.3))
    for j in range(-2,3):
        a=iso(-3.55,j,.23); b=iso(3.55,j,.23)
        body.append(line(a[0],a[1],b[0],b[1],"#a99b86",1,.3))

    # pipes behind modules
    def pipe(a,b,color="#2b2722",w=7,glow=None,dash=None):
        d=f"M {a[0]} {a[1]} C {(a[0]+b[0])/2} {a[1]-55} {(a[0]+b[0])/2} {b[1]-55} {b[0]} {b[1]}"
        out=path(d,"none",color,w,1,dash,'stroke-linecap="round"')
        if glow: out+=path(d,"none",glow,2.2,1,dash,'stroke-linecap="round" filter="url(#glow)"')
        return out
    p_tools=iso(-1.65,.7,1.15); p_core_l=iso(-.65,-.55,1.85)
    p_core_r=iso(.65,-.55,1.85); p_mem=iso(1.9,.7,1.35)
    p_core_b=iso(0,-1.35,1.05); p_ans=iso(0,1.35,.9)
    p_ans_r=iso(.55,1.9,.8); p_ext=iso(1.3,1.85,.8)
    p_ext_mem=iso(1.6,1.55,1.1)
    p_guard=iso(-1.85,1.7,.85); p_core_gl=iso(-.95,-.2,1.3)
    body.append(pipe(p_tools,p_core_l,"#2b2722",7,"#ff7a3a"))
    body.append(pipe(p_core_r,p_mem,"#2b2722",7,"#5ad8a6"))
    body.append(pipe(p_core_b,p_ans,"#2b2722",7,"#5b8ff9"))
    body.append(pipe(p_ans_r,p_ext,"#2b2722",6,"#b37feb"))
    body.append(pipe(p_ext_mem,p_mem,"#2b2722",6,"#5ad8a6"))

    # modules back-to-front
    # LLM core (center back)
    body.append(shadow(760,680,110,34,.2))
    body.append(box(-.65,-1.35,1.0,1.3,1.3,.95,"#3a352e","#211e1a","#2c2822"))
    # orange top core panel
    a=iso(-.42,-1.35,1.96); b=iso(.22,-1.35,1.96); c=iso(.22,-.95,1.96); d=iso(-.42,-.95,1.96)
    body.append(f'<polygon points="{pts([a,b,c,d])}" fill="#ff6a2a" opacity=".9" filter="url(#glow)"/>')
    body.append(txt(704,472,"LLM",26,"#fff",900,anchor="middle",family=MONO))
    body.append(txt(704,494,"+ CONTEXT",8.5,"#ffd7c2",700,anchor="middle",family=MONO,spacing="1.6"))
    # tools left
    body.append(shadow(470,650,80,28,.13))
    body.append(box(-2.55,.35,.5,1.1,1.1,.65,"#f6c37a","#d98a2b","#e8a64a"))
    for k in range(3):
        a=iso(-2.32+.2*k,.55,1.16); b=iso(-2.18+.2*k,.55,1.16); c=iso(-2.18+.2*k,.72,1.16); d=iso(-2.32+.2*k,.72,1.16)
        body.append(f'<polygon points="{pts([a,b,c,d])}" fill="#5f3c16" opacity=".55"/>')
    # memory stack right
    body.append(shadow(930,670,90,28,.13))
    for k,sh in enumerate(["#b9d8c4","#a9d0b8","#97c5aa"]):
        body.append(box(1.35,-.35,.55+k*.22,1.2,1.2,.17,sh,"#6f9d7f","#84b394"))
    # guard left front
    body.append(shadow(380,780,55,20,.12))
    body.append(box(-2.95,1.55,.42,.72,.72,.52,"#f4d38a","#c99a3a","#dfb45a"))
    body.append(circle(*iso(-2.6,1.9,.95),7,"#fff4d8","#c99a3a",2))
    # answer front
    body.append(shadow(570,790,80,26,.13))
    body.append(box(-.55,1.35,.42,1.1,.95,.55,"#c9d6ee","#7d9bd1","#9fb6df"))
    # extractor right front
    body.append(shadow(780,820,65,22,.12))
    body.append(box(1.2,1.45,.4,.9,.9,.55,"#e6d2f5","#9d79bd","#b996d4"))

    # labels on solid tops
    def top_label(x,y,z,s,size=8.5,fill="#2b2722"):
        px,py=iso(x,y,z)
        body.append(txt(px,py+3,s,size,fill,900,anchor="middle",family=MONO,spacing="1.2"))
    top_label(-2.0,.9,1.17,"TOOLS",8.5,"#5f3c16")
    top_label(1.95,.25,1.36,"MEMORY",8.5,"#3f6b4f")
    top_label(-2.09,1.91,.95,"GUARD",7.5,"#7b5a1c")
    top_label(0,1.82,.99,"ANSWER",8.5,"#3f5377")
    top_label(1.65,1.9,.96,"EXTRACT",7.5,"#6b438a")

    # packets
    for (x,y),c in [(p_tools,"#ffb347"),(p_core_r,"#ffd166"),(p_ans,"#8fb3ff"),(p_ext_mem,"#9be6bd"),(p_guard,"#ffe08a")]:
        body.append(circle(x,y,5,"#fff",c,3,1,'filter="url(#glow)"'))
        body.append(circle(x,y,2.4,c))

    # callouts
    def callout(x,y,title,sub,line_to,color="#2b2722"):
        body.append(line(x,y,x+38,y,color,1,1))
        body.append(circle(x+38,y,2,color))
        body.append(line(x+38,y,line_to[0],line_to[1],color,1,.3,"3 4"))
        body.append(txt(x,y-7,title,10.5,color,900,spacing="1.2"))
        body.append(txt(x,y+11,sub,9.5,"#7a6f60"))
    callout(930,330,"01 · LLM + CONTEXT","模型 / messages / tools",(840,500))
    callout(150,410,"02 · TOOLS","read / write / run",(420,560))
    callout(1130,430,"03 · MEMORY","Chroma / embedding",(1010,560))
    callout(480,805,"04 · ANSWER","真实 stdout",(560,730))
    callout(920,800,"05 · EXTRACTOR","keep / tags / store",(820,740))
    callout(150,680,"06 · GUARD","max_steps / truncate",(335,760))

    body.append(txt(56,920,"A working object, not a diagram: each pipe carries a packet, each module has a state.",11,"#5f5548"))
    body.append(txt(56,950,"source: wheresryan22/anatomy  ·  isometric SVG; optional WebGL layer",9.5,"#8e8373",family=MONO))
    body.append(rect(1080,888,260,58,"#fffdf7","#d9cdbb",1,8))
    body.append(txt(1094,910,"LOOP",9.5,"#8a7f6e",900,spacing="1.8"))
    body.append(txt(1094,932,"Tools → LLM → Answer → Memory",9,"#2b2722",family=MONO))
    return svg(W,H,''.join(body),"#f4eee2")

if __name__=="__main__":
    (ROOT/"01-antv-chart"/"chart.svg").write_text(chart(),encoding="utf-8")
    (ROOT/"02-excalidraw"/"diagram.svg").write_text(excalidraw(),encoding="utf-8")
    (ROOT/"03-mermaid"/"sequence.svg").write_text(mermaid(),encoding="utf-8")
    (ROOT/"04-anatomy"/"anatomy.svg").write_text(anatomy(),encoding="utf-8")
    print("wrote 4 svgs")
