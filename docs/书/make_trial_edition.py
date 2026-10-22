#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'docs/书/Agent入门-初稿.md'
OUT=ROOT/'docs/书/Agent入门-试读版-2026-10-22.md'
TRIAL=ROOT/'docs/08-日志/编辑试点-第12讲-改写稿.md'

NAV={
0:("这本书怎么读？","知道全书五拍主线，并能按问题跳读。"),
1:("LLM 为什么只会说？","理解开环，以及 Agent 要补的第一条回路。"),
2:("一个循环 + 一份工具清单，怎么让它动手？","看懂最小 Agent 的 88 行骨架。"),
3:("工具返回的字符串，程序怎么用？","理解感知契约和 {ok,data,error}。"),
4:("历史为什么先撞墙？","知道上下文预算、截断和压缩的代价。"),
5:("关掉就忘，怎么办？","理解为什么需要外置长期记忆。"),
6:("记忆不能全存，写侧记什么？","看懂抽取、过滤和 keep 的判断。"),
7:("存了不一定召得回，读侧怎么召回？","理解 top-k、阈值和文本增富。"),
8:("换更强 embedding，值不值？","知道召回率、延迟和成本的三角。"),
9:("跨轮“它”到底指谁？","理解记忆切分和指代消解。"),
10:("记忆策略改了，怎么知道变好？","会用端到端记忆用例评测。"),
11:("加精排一定更好吗？","知道 rerank 被否决的边界。"),
12:("什么条件下，拆成多个 Agent 才划算？","会用四条拆分判据和四条循环否决线。"),
13:("Router 判断一次要花多少钱？","理解 853 token 的判断税和 0 token 预筛。"),
14:("Fan-out 是真并行还是假并行？","分得清墙钟时间、认知负担和串行 for。"),
15:("同模型 EC 在客观题上靠谱吗？","知道 0/6 的边界和外部独立信号。"),
16:("层级/工人池，什么时候值？","理解慢工具才值的条件。"),
17:("去中心化 Group Chat，什么时候必要？","知道协商成本和广播的代价。"),
18:("中央无法评估时，合同网怎么用？","理解招标/投标/中标的结构。"),
19:("辩论真的提升正确率吗？","知道必要性未复现的负结果。"),
20:("黑板的关键变量是什么？","理解反应式控制，而不是“多人聊天”。"),
21:("模型变强后，哪些脚手架被吃掉？","分清推理轴和工程轴。"),
22:("怎么不让 Agent 跑飞、烧钱？","会用预算、截断和收尾步。"),
23:("工具越来越多，怎么把 N×M 变成 N+M？","理解 MCP 的协议价值。"),
24:("什么该做成 MCP 工具？","知道协议边界和 schema 膨胀。"),
25:("模块越来越多，怎么组织？","理解四层架构和纯叶子。"),
26:("怎么知道它行不行？","知道监控、评测、回归门的区别。"),
27:("九句话和被证伪的判断是什么？","能复述全书结论和负结果。"),
28:("模型变强后，还剩下什么？","理解工程轴为什么更值钱。"),
29:("生产级 harness 长什么样？","知道事件日志、门禁、状态和权限。"),
30:("从 DSH 吸收什么？","知道哪些机制值得搬、哪些不该搬。"),
31:("怎么把 Agent 流程拍下来？","理解回放、时序和可视化。"),
32:("长任务、状态、安全还缺什么？","知道 RunState、checkpoint、resume 和权限门。"),
}

FIG={
'../diagrams/教学-Agent本质.png':'../diagrams/v2/agent-essence-card.png',
'../diagrams/教学-四种编排.png':'../diagrams/v2/four-patterns-card.png',
'../diagrams/教学-记忆两次.png':'../diagrams/v2/memory-twice-card.png',
'../diagrams/教学-评测闭环.png':'../diagrams/v2/eval-loop-card.png',
'../diagrams/architecture-overview.png':'../diagrams/v2/architecture-card.png',
'../diagrams/model-vs-agents-axes.png':'../diagrams/v2/axes-card.png',
'../diagrams/教学-黑板三臂.png':'../diagrams/v2/blackboard-card.png',
'../diagrams/教学-能力编排矩阵.png':'../diagrams/v2/matrix-card.png',
'../diagrams/model-vs-agents-horizon.png':'../diagrams/v2/horizon-card.png',
'../diagrams/model-vs-agents-selfcorrect.png':'../diagrams/v2/selfcorrect-card.png',
}

def nav_card(num, include_prev=True):
    if num not in NAV or num>32: return ''
    q, take = NAV[num]
    prev = f'第 {num-1} 讲' if num-1 in NAV else '序章'
    nxt = f'第 {num+1} 讲' if num+1 in NAV else '附录'
    lines=[]
    if include_prev:
        lines.append(f'> **前情**：接着{prev}的问题往下走。')
    lines += [f'> **本讲只回答**：{q}', f'> **读完后你能**：{take}', f'> **下一讲**：{nxt}会接着这个问题。']
    return '  \n'.join(lines)

def inject_nav(seg):
    m=re.match(r'## 第 (\d+) 讲',seg)
    if not m: return seg
    num=int(m.group(1))
    if num not in NAV or num>32: return seg
    head=seg[:2600]
    if '本章只回答' in head or '本讲只回答' in head:
        return seg
    # insert after title, status, and any initial blockquote/blank lines
    lines=seg.splitlines()
    i=1
    # skip blank and blockquote status block
    while i < len(lines) and (lines[i].strip()=='' or lines[i].startswith('>')):
        i+=1
    lines.insert(i, '')
    lines.insert(i+1, nav_card(num, include_prev=('前情' not in head)))
    lines.insert(i+2, '')
    return '\n'.join(lines)

def main():
    s=SRC.read_text(encoding='utf-8')
    # replace header up to TOC
    toc_i=s.index('## 目录')
    preface='''# Agent 入门（结构 / 视觉试读版）

> **版本：2026-10-22 试读版 · 6 篇 32 讲。** 这不是终稿。
> 这一版只做三件事：统一讲前卡、重写第 12 讲、统一书中插图。
> 其余正文仍是初稿内容，没有逐讲重写；标 ⬜ 的仍是待写。
>
> **本版改了什么**
> 1. 32 讲统一增加/保留“前情 → 本讲只回答 → 读完后你能 → 下一讲”讲前卡；
> 2. 第 12 讲按试读方案重写：判据前置、四模式地图、Pipeline 最小例、决策树；
> 3. 书中 12 张图统一成手绘卡片风格：4 张核心图重绘，6 张保留内容加统一框，
>    第 12 讲决策树用手绘版；
> 4. 其余讲正文未重写，只做结构入口和图片替换。
>
> **读法**：先看第 0 讲地图；再按 6 篇顺序读。每讲先看讲前卡，再看正文。
> 复习时只看每讲开头和结尾的“代价 / 下一讲”。
>
> **编辑方案**：[全书目录与主线](../00-索引/全书目录与主线.md) ·
> **编辑试点报告**：[编辑试点-第12讲](../08-日志/编辑试点-第12讲.md) ·
> **项目日志**：[项目日志 2026](../08-日志/项目日志-2026.md)

---

'''
    s=preface+s[toc_i:]
    # replace 12 lecture with trial
    trial=TRIAL.read_text(encoding='utf-8')
    trial=re.sub(r'^# ', '## ', trial, count=1, flags=re.M)
    trial=trial.replace('\n## ', '\n### ')
    trial=trial.replace('## 第 12 讲 ', '## 第 12 讲 · ', 1)
    trial=trial.replace('**试点稿**：按 P0 建议重写，**未合并**。','**试读稿**：按试读方案重写；')
    start=s.index('## 第 12 讲')
    end=s.index('## 第 13 讲', start)
    a13=s.rfind('<a id="j-13"></a>', start, end)
    if a13!=-1: end=a13
    s=s[:start]+trial.rstrip()+'\n\n---\n\n'+s[end:]
    s=s.replace('<a id="j-12"></a>##', '<a id="j-12"></a>\n\n##')
    s=s.replace('<a id="j-12"></a>## ', '<a id="j-12"></a>\n\n## ')
    # figure map
    for a,b in FIG.items(): s=s.replace(a,b)
    # split and inject nav
    parts=re.split(r'(?=^## 第 \d+ 讲)',s,flags=re.M)
    s=''.join(inject_nav(p) if p.startswith('## 第 ') else p for p in parts)
    # TOC line for 12
    s=s.replace('- [第 12 讲 · 四种基本编排：Router / Pipeline / Fan-out / EC](#j-12) 🟡',
                '- [第 12 讲 · 什么时候该拆：四种编排速览](#j-12) 🟡')
    s=s.replace('<a id="j-12"></a>##', '<a id="j-12"></a>\n\n##')
    s=s.replace('（试点改写，未合并）','（试读版）')
    OUT.write_text(s,encoding='utf-8')
    print('written',OUT,len(s),'chars',len(s.splitlines()),'lines')
    print('nav cards',sum(1 for p in re.split(r'(?=^## 第 \d+ 讲)',s,flags=re.M) if '**本讲只回答**' in p[:2600]))

if __name__=='__main__': main()
