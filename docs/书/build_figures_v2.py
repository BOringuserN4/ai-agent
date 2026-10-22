#!/usr/bin/env python3
from pathlib import Path
import base64, html, math, random, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'docs/diagrams'
V2=D/'v2'
PAPER='#fffdf8'
INK='#2f2b26'
FONT="'PingFang SC','STHeiti','Heiti SC',sans-serif"
HAND="'Chalkboard SE','Chalkboard','STHeiti',sans-serif"
MONO="'SF Mono','Menlo','Courier New',monospace"
PIL_FONT='/System/Library/Fonts/STHeiti Medium.ttc'

def e(s): return html.escape(str(s))
def txt(x,y,s,size=14,fill=INK,weight=700,anchor='start',family=FONT,spacing=None):
    sp=f' letter-spacing="{spacing}"' if spacing else ''
    return f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{sp}>{e(s)}</text>'
def rect(x,y,w,h,fill,stroke=INK,sw=2,rx=12,extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'
def path(d,color=INK,sw=2,marker=True,dash=None):
    dd=f' stroke-dasharray="{dash}"' if dash else ''
    m=' marker-end="url(#arrow)"' if marker else ''
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"{m}{dd}/>'
def box(x,y,w,h,fill,stroke,label,sub='',size=18,subsize=11):
    s=rect(x,y,w,h,fill,stroke,2.2,12,'filter="url(#rough)"')
    s+=txt(x+w/2,y+h/2-(4 if sub else -6),label,size,INK,800,'middle',HAND)
    if sub: s+=txt(x+w/2,y+h/2+22,sub,subsize,'#6f675c',500,'middle')
    return s
def h_arrow(x1,x2,y,color=INK,label=None,label_y=None,dash=None):
    s=path(f"M {x1} {y} L {x2} {y}",color,2,True,dash)
    if label: s+=txt((x1+x2)/2,label_y if label_y is not None else y-10,label,11,color,700,'middle')
    return s
def v_arrow(x,y1,y2,color=INK,label=None,label_x=None,dash=None):
    s=path(f"M {x} {y1} L {x} {y2}",color,2,True,dash)
    if label: s+=txt(label_x if label_x is not None else x+10,(y1+y2)/2,label,11,color,700,'start')
    return s
def elbow(x1,y1,x2,y2,color=INK,r=16,label=None,down=True):
    if down:
        d=f"M {x1} {y1} L {x2} {y1} Q {x2} {y1} {x2} {y1+r} L {x2} {y2}"
    else:
        d=f"M {x1} {y1} L {x2} {y1} Q {x2} {y1} {x2} {y1-r} L {x2} {y2}"
    s=path(d,color,2)
    if label: s+=txt((x1+x2)/2,y1-10,label,11,color,700,'middle')
    return s

def svg_doc(body,w=1400,h=800):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
<filter id="rough" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="2" seed="8" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="1.7"/></filter>
<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{INK}"/></marker>
</defs>
<rect width="{w}" height="{h}" fill="{PAPER}"/>
{body}
</svg>'''

def agent_essence():
    b=[]
    b.append(box(40,290,220,150,'#e4edff','#4f7fd6','Prompt','角色 / 格式 / 约束',20))
    b.append(box(410,250,430,220,'#fbe8cb','#d98a2b','LLM（大脑）','读懂 → 决策 → 写参数',24))
    b.append(box(1040,290,300,150,'#dff0e5','#4e9a6a','工具（手）','calculator / weather / MCP',20))
    b.append(box(500,620,330,120,'#f3e8ff','#8b5fb5','记忆（上下文）','短期 history + 长期检索',18))
    b.append(h_arrow(260,410,350,'#4f7fd6','角色约束',338))
    b.append(h_arrow(840,1040,330,'#d98a2b','function call',318))
    b.append(h_arrow(1040,840,390,'#4e9a6a','结果回流',378))
    b.append(v_arrow(640,470,618,'#3f6b4f','沉淀',650))
    b.append(v_arrow(760,618,470,'#6b438a','召回',772,'6 5'))
    return svg_doc(''.join(b))

def four_patterns():
    b=[]
    # panels
    def panel(x,y,w,h,title,sub,color):
        return rect(x,y,w,h,PAPER,'#d8d0c2',1.4,14)+txt(x+18,y+30,title,15,color,900)+txt(x+18,y+50,sub,10,'#8a7f6e',400)
    b.append(panel(30,30,660,350,'Router','LLM 决定拆不拆 / 拆给谁','#4f7fd6'))
    b.append(panel(710,30,660,350,'Pipeline','代码写死顺序，上一步喂下一步','#d98a2b'))
    b.append(panel(30,410,660,350,'Fan-out / Fan-in','切分 → 分发 → 汇聚','#4e9a6a'))
    b.append(panel(710,410,660,350,'Evaluator-Critic','生成 → 批判 → 重做','#8b5fb5'))
    # Router mini
    b.append(box(60,150,120,54,'#e4edff','#4f7fd6','TASK',size=13))
    b.append(box(230,150,120,54,'#fbe8cb','#d98a2b','Router',size=13))
    b.append(box(400,105,110,46,'#dff0e5','#4e9a6a','A',size=13)); b.append(box(400,185,110,46,'#dff0e5','#4e9a6a','B',size=13))
    b.append(box(550,150,100,54,'#f3e8ff','#8b5fb5','merge',size=13))
    b.append(h_arrow(180,230,177,'#4f7fd6')); b.append(h_arrow(350,400,177,'#4f7fd6'))
    b.append(path('M 510 128 L 535 128 L 535 177','#4f7fd6',2)); b.append(path('M 510 208 L 535 208 L 535 177','#4f7fd6',2))
    # Pipeline
    for i,(tx,lab) in enumerate([(760,'step 1'),(910,'step 2'),(1060,'step 3')]):
        b.append(box(tx,150,120,54,'#fbe8cb','#d98a2b',lab,size=13))
        if i<2: b.append(h_arrow(tx+120,tx+150,177,'#d98a2b'))
    # Fan-out
    b.append(box(60,540,120,54,'#e4edff','#4f7fd6','TASK',size=13))
    b.append(box(220,540,100,54,'#dff0e5','#4e9a6a','split',size=13))
    for i,y in enumerate([480,535,590]): b.append(box(370,y,100,38,'#dff0e5','#4e9a6a',chr(65+i),size=12))
    b.append(box(530,540,100,54,'#f3e8ff','#8b5fb5','merge',size=13))
    b.append(h_arrow(180,220,567,'#4e9a6a'))
    b.append(path('M 320 567 L 345 567 L 345 499 L 370 499','#4e9a6a',2))
    b.append(path('M 320 567 L 370 554','#4e9a6a',2))
    b.append(path('M 320 567 L 345 567 L 345 609 L 370 609','#4e9a6a',2))
    b.append(path('M 470 499 L 500 499 L 500 567 L 530 567','#4e9a6a',2))
    b.append(path('M 470 554 L 530 567','#4e9a6a',2))
    b.append(path('M 470 609 L 500 609 L 500 567 L 530 567','#4e9a6a',2))
    # EC
    b.append(box(760,530,120,54,'#e4edff','#4f7fd6','generate',size=12))
    b.append(box(930,530,120,54,'#fbe8cb','#d98a2b','critic',size=12))
    b.append(box(1100,530,120,54,'#f3e8ff','#8b5fb5','revise',size=12))
    b.append(h_arrow(880,930,557,'#8b5fb5'))
    b.append(h_arrow(1050,1100,557,'#8b5fb5'))
    b.append(path('M 1160 584 L 1160 660 L 820 660 L 820 584','#8b5fb5',2))
    b.append(txt(980,690,'不过线就带着批评重做，直到封顶',10,'#8a7f6e',400,'middle'))
    return svg_doc(''.join(b))

def memory_twice():
    b=[]
    b.append(txt(40,50,'提问前：召回',16,'#3f6b4f',900)); b.append(txt(40,72,'Query → Memory → Filter → LLM',10,'#8a7f6e',400))
    b.append(txt(40,440,'回答后：沉淀',16,'#3f5377',900)); b.append(txt(40,462,'Answer → Extractor → Keep → Memory',10,'#8a7f6e',400))
    # top
    b.append(box(40,130,160,60,'#e4edff','#4f7fd6','Query',size=14))
    b.append(box(290,130,190,60,'#dff0e5','#4e9a6a','Memory',size=14))
    b.append(box(570,130,170,60,'#fbe8cb','#d98a2b','Filter',size=14))
    b.append(box(830,130,170,60,'#f3e8ff','#8b5fb5','LLM',size=14))
    b.append(h_arrow(200,290,160,'#4f7fd6','query',148))
    b.append(h_arrow(480,570,160,'#4e9a6a','top-k',148))
    b.append(h_arrow(740,830,160,'#d98a2b','hit',148))
    b.append(txt(1020,160,'阈值 / 文本增富',11,'#8a7f6e',400))
    # bottom
    b.append(box(40,520,160,60,'#e4edff','#4f7fd6','Answer',size=13))
    b.append(box(280,520,210,60,'#fbe8cb','#d98a2b','Extractor',size=13))
    b.append(box(570,520,170,60,'#dff0e5','#4e9a6a','Keep',size=14))
    b.append(box(830,520,190,60,'#f3e8ff','#8b5fb5','Memory',size=13))
    b.append(h_arrow(200,280,550,'#4f7fd6','write',538))
    b.append(h_arrow(490,570,550,'#d98a2b','keep?',538))
    b.append(h_arrow(740,830,550,'#4e9a6a','store',538))
    return svg_doc(''.join(b))

def eval_loop():
    b=[]
    boxes=[('case',60,180,'#e4edff','#4f7fd6'),('run',320,180,'#fbe8cb','#d98a2b'),
           ('score',580,180,'#dff0e5','#4e9a6a'),('diagnose',580,500,'#f3e8ff','#8b5fb5'),
           ('fix',340,500,'#fbe8cb','#d98a2b'),('rerun',80,500,'#e4edff','#4f7fd6')]
    for name,x,y,fill,stroke in boxes: b.append(box(x,y,160,64,fill,stroke,name,size=16))
    b.append(h_arrow(220,320,212,'#4f7fd6'))
    b.append(h_arrow(480,580,212,'#d98a2b'))
    b.append(v_arrow(660,244,500,'#4e9a6a'))
    b.append(h_arrow(580,500,532,'#8b5fb5'))
    b.append(h_arrow(340,240,532,'#8b5fb5'))
    b.append(path('M 160 500 L 160 400 L 400 400 L 400 244','#4f7fd6',2))
    b.append(txt(175,430,'rerun',10,'#4f7fd6',700,'middle'))
    b.append(txt(280,330,'n / golden set',11,'#8a7f6e',400))
    b.append(txt(800,330,'分数不是终点',13,'#5f5548',800))
    b.append(txt(800,354,'诊断才是；回归门要能挡住变坏',10.5,'#8a7f6e',400))
    b.append(txt(800,378,'判分器要校准',10.5,'#8a7f6e',400))
    return svg_doc(''.join(b))

# ---- raster helpers ----
def svg_to_png(svg_text,name,w=1400,h=800):
    # square wrapper avoids Quick Look crop
    b64=base64.b64encode(svg_text.encode()).decode()
    pad=(1600-h)//2
    wrap=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1600"><rect width="1600" height="1600" fill="{PAPER}"/><image href="data:image/svg+xml;base64,{b64}" x="100" y="{pad}" width="1400" height="{h}"/></svg>'''
    sp=V2/f'_{name}.svg'; sp.write_text(wrap,encoding='utf-8')
    subprocess.run(['qlmanage','-t','-s','1600','-o',str(V2),str(sp)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    png=sp.with_suffix('.svg.png')
    im=Image.open(png).convert('RGB').crop((100,pad,1500,pad+h))
    out=V2/f'{name}.png'; im.save(out)
    sp.unlink(missing_ok=True); png.unlink(missing_ok=True)
    return out

def hand_border(draw,w,h):
    random.seed(4)
    m=26
    pts=[(m,m),(w-m,m),(w-m,h-m),(m,h-m)]
    for i in range(4):
        a=pts[i]; b=pts[(i+1)%4]
        line=[]
        for k in range(36):
            t=k/35
            x=a[0]+(b[0]-a[0])*t+random.uniform(-1.8,1.8)
            y=a[1]+(b[1]-a[1])*t+random.uniform(-1.8,1.8)
            line.append((x,y))
            if k%4==0: draw.ellipse([x-1.2,y-1.2,x+1.2,y+1.2],fill='#2f2b26')
        draw.line(line,fill='#2f2b26',width=2)

def frame_image(src,out,fig,title,caption,big_title=True):
    W,H=1600,1100
    im=Image.new('RGB',(W,H),'#fffdf8'); d=ImageDraw.Draw(im)
    # paper dots
    for y in range(30,H,30):
        for x in range(30,W,30): d.ellipse([x,y,x+1.5,y+1.5],fill='#2f2b26')
    # border
    hand_border(d,W,H)
    # title
    f_title=ImageFont.truetype(PIL_FONT,38); f_small=ImageFont.truetype(PIL_FONT,15); f_cap=ImageFont.truetype(PIL_FONT,18)
    if big_title:
        d.text((70,50),title,font=f_title,fill='#2f2b26')
    else:
        d.text((70,54),f'{fig} · {title}',font=ImageFont.truetype(PIL_FONT,19),fill='#7a6f60')
    d.text((W-70,58),fig,font=f_small,fill='#8a7f6e',anchor='ra')
    # image
    img=Image.open(src).convert('RGB')
    area=(90,110,1510,950) if not big_title else (90,140,1510,950)
    img.thumbnail((area[2]-area[0],area[3]-area[1]),Image.LANCZOS)
    x=area[0]+(area[2]-area[0]-img.width)//2
    y=area[1]+(area[3]-area[1]-img.height)//2
    im.paste(img,(x,y))
    d.text((70,1015),caption,font=f_cap,fill='#5f5548')
    d.text((W-70,1040),'ANATOMY · HAND-DRAWN FIGURE SYSTEM',font=f_small,fill='#9a8f7f',anchor='ra')
    im.save(out)

if __name__=='__main__':
    specs=[
        ('agent-essence',agent_essence(),'FIG. 1','Agent 的本质：一个循环 + 一份工具清单','去掉所有框架，Agent 就这四样：大脑、手、记忆、循环。'),
        ('four-patterns',four_patterns(),'FIG. 2','四种编排模式：一张图看懂','先问单 Agent 做不到什么，再看四种形状各自的成本。'),
        ('memory-twice',memory_twice(),'FIG. 3','记忆用两次：提问前召回，回答后沉淀','记忆不是“存一次”，是两条回路。'),
        ('eval-loop',eval_loop(),'FIG. 4','评测闭环：从“看见”到“改对”','分数不是终点，诊断才是。'),
    ]
    for name,svg,fig,title,cap in specs:
        p=svg_to_png(svg,name)
        frame_image(p,V2/f'{name}-card.png',fig,title,cap)
        print('figure',V2/f'{name}-card.png')

    existing=[
        ('architecture-overview.png','architecture-card.png','FIG. 5','四层架构 + 运行时数据流','模块多了，先分层；纯叶子只做事，不做决定。'),
        ('model-vs-agents-axes.png','axes-card.png','FIG. 6','模型变强，两类脚手架的走向','推理类脚手架被吃掉，工程类更值钱。'),
        ('教学-黑板三臂.png','blackboard-card.png','FIG. 7','黑板调查：三臂对照','0/6、4/6、5/6；关键变量是反应式控制。'),
        ('教学-能力编排矩阵.png','matrix-card.png','FIG. 8','能力 × 编排：2×2 对照','强模型 + 强编排 18/18；弱模型 + 强编排 17/18；EC 0/6。'),
        ('model-vs-agents-horizon.png','horizon-card.png','FIG. 9','长任务的塌缩：p<1 就是数学必然','每一步 p<1，任务越长越接近 0。'),
        ('model-vs-agents-selfcorrect.png','selfcorrect-card.png','FIG. 10','自更正的两步：找错 vs 纠错','找错是瓶颈，纠错要外部定位。'),
    ]
    for src,out,fig,title,cap in existing:
        frame_image(D/src,V2/out,fig,title,cap,big_title=False)
        print('framed',V2/out)
