#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_figures_v2 import svg_doc, svg_to_png, frame_image, txt, rect, path, V2, PAPER, INK, FONT, HAND, MONO

def layer(y,num,title,chips,fill,stroke,dark=False):
    s=rect(150,y,1100,58,fill,stroke,2,12,'filter="url(#rough)"')
    s+=txt(176,y+25,title,13,'#fff' if dark else INK,900)
    s+=txt(176,y+45,chips,9.8,'#e8e1d5' if dark else '#6f675c',500)
    s+=f'<circle cx="112" cy="{y+29}" r="15" fill="{PAPER}" stroke="{stroke}" stroke-width="1.6"/>'
    s+=txt(112,y+34,f'{num:02d}',10,stroke,900,'middle',MONO)
    return s

def architecture():
    b=[]
    rows=[
      (40,'UI / Transport','Web GUI · ACP · SDK · headless','#e4edff','#4f7fd6',False),
      (116,'API / Session Controller','会话列表 · 投影 · 控制面','#eef3fb','#7d9bd1',False),
      (192,'Agent Registry + AgentLoop','turn / step · inbox · 工具调度','#fbe8cb','#d98a2b',False),
      (268,'Session Log + Projections','仅追加事件 · JSONL 持久化 · 投影','#f3e8ff','#8b5fb5',False),
      (344,'Context Assembly','system prompt · AGENTS.md · skills · token meter · compaction · spill','#fff3d8','#c99a3a',False),
      (420,'Tool Runtime','fs · bash · web · subagent · workflow · jobs + permission / approval / sandbox','#dff0e5','#4e9a6a',False),
      (496,'LLM Runtime','Provider Adapter · Stream · Retry','#3a352e','#3a352e',True),
      (572,'Observability','OTel · Session Telemetry · Stats','#f7dcd8','#c85445',False),
    ]
    for i,(y,t,c,f,st,dark) in enumerate(rows,1): b.append(layer(y,i,t,c,f,st,dark))
    # side arrows
    b.append(path('M 60 78 L 60 620','#4f7fd6',2))
    b.append(txt(44,360,'request ↓',10,'#4f7fd6',800,'middle',MONO))
    b.append(path('M 1320 620 L 1320 78','#4e9a6a',2))
    b.append(txt(1336,360,'events ↑',10,'#4e9a6a',800,'middle',MONO))
    # footer
    b.append(rect(150,666,1100,40,'#fffdf8','#d8d0c2',1.2,8))
    b.append(txt(168,691,'插件组合：dsh-base（基础插件行） → profile（增删） → agent-preset（单 Agent 子插件）',10.5,'#5f574c',700))
    b.append(txt(168,748,'一条铁律：模型可见即已记录；请求是冻结的纯函数；事件是唯一事实源。',11,'#5f5748',700))
    return svg_doc(''.join(b))

def step_flow():
    b=[]
    steps=[
      ('claim inbox','领取输入：用户消息 / steering / 排队工作'),
      ('agent/pre-step','可拦截、可改写；写事件'),
      ('agent/request waterfall','模型 / 参数解析，监听器只能读'),
      ('prepareCall','适配器校验、默认值'),
      ('assemble system prompt + tools','AGENTS.md / skills / 工具 schema'),
      ('derive messages','从会话日志派生，不另存一份历史'),
      ('stream LLM','流式输出；取消是协作式的'),
      ('tool calls','独占 or 并行安全；结果写回日志'),
      ('write events','模型可见即已记录'),
      ('next step / end','下一步，或收束'),
    ]
    x,w=210,980; y=34; h=44; gap=30
    for i,(title,sub) in enumerate(steps):
        yy=y+i*(h+gap)
        last=i==len(steps)-1
        fill='#dff0e5' if last else ('#fff3d8' if i%2 else '#eef3fb')
        stroke='#4e9a6a' if last else ('#c99a3a' if i%2 else '#7d9bd1')
        b.append(rect(x,yy,w,h,fill,stroke,1.8,10,'filter="url(#rough)"'))
        b.append(f'<circle cx="{x-30}" cy="{yy+h/2}" r="13" fill="{PAPER}" stroke="{stroke}" stroke-width="1.5"/>')
        b.append(txt(x-30,yy+h/2+4,str(i+1),9.5,stroke,900,'middle',MONO))
        b.append(txt(x+18,yy+19,title,12,INK,800,family=MONO))
        b.append(txt(x+18,yy+35,sub,9.2,'#6f675c',400))
    for i in range(len(steps)-1):
        yy=y+i*(h+gap)
        stroke='#c99a3a' if i%2 else '#7d9bd1'
        b.append(path(f'M {x+w/2} {yy+h+1} L {x+w/2} {yy+h+gap-1}',stroke,1.8))
    b.append(txt(210,766,'每一步都写事件；turn/step 是有边界的状态机，不是 while True。',11,'#5f5748',700))
    b.append(txt(210,788,'重试与压缩都在步骤边界发生；崩溃不会留下不可见的重试。',9.5,'#8a7f6e',400))
    return svg_doc(''.join(b))

if __name__=='__main__':
    for name,svg,fig,title,cap in [
      ('dsh-architecture',architecture(),'FIG. 29-1','DSH 总体架构：事件溯源 + 能力接口 + 插件组合','分层是职责，不是目录；事件是唯一事实源。'),
      ('dsh-step',step_flow(),'FIG. 29-2','DSH 的一个 Step：从 claim inbox 到写回事件','turn/step 是有边界的状态机，不是 while True。'),
    ]:
        p=svg_to_png(svg,name)
        frame_image(p,V2/f'{name}-card.png',fig,title,cap)
        print('wrote',V2/f'{name}-card.png')
