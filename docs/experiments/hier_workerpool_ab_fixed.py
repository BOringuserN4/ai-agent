# -*- coding: utf-8 -*-
"""工人池 A/B（固定计划版，2026/10/05）—— 隔离「工人池」单一变量

发现 Router 拆分不稳定（有时 3 任务/有时 1 solo），会掩盖工人池效果。
故本实验**固定计划**（3×weather + 1×solo），只切换工人池开关：

  · 旧：按 expert 去重（3→1 weather）+ 共享单例  → 实际串行
  · 新：保留同域多子任务 + 每子任务独立 worker    → 真并行

指标：墙钟、各 worker 工具调用、是否真并行。
"""
import os, sys, time, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
import agent.multi_agent as mam
from agent.multi_agent import MultiAgent

CITIES = ["北京", "上海", "广州"]
FIXED = ([{"expert": "weather", "subtask": f"查询{city}当前气温，并判断是否适合户外活动（15~28℃）"}
          for city in CITIES]
         + [{"expert": "solo", "subtask": "汇总北京、上海、广州三城气温并给对比结论"}])
N = int(os.getenv("AB_N", "3"))
OUT = os.path.join(ROOT, "tmp-artifacts", "workerpool_fixed_ab.txt")


def dedup(tasks):
    seen, out = set(), []
    for t in tasks:
        if t["expert"] in seen:
            continue
        seen.add(t["expert"]); out.append(t)
    return out


def run_arm(flag, tag, fh):
    mam.ALLOW_PARALLEL_SAME_ROLE = flag
    tasks = FIXED if flag else dedup(FIXED)
    walls = []
    for i in range(N):
        ma = MultiAgent(use_memory=False)
        with contextlib.redirect_stdout(io.StringIO()):
            t0 = time.time()
            parts = ma._fanout_parallel(tasks)
            wall = round(time.time() - t0, 2)
        calls = {}
        for name, w in ma._run_workers:
            calls[name] = calls.get(name, 0) + sum(1 for s in w.tracer.steps if s.type == "tool_call")
        walls.append(wall)
        fh.write(f"[{tag}] 跑{i+1}: 执行任务={len(tasks)} 墙钟={wall}s "
                 f"worker调用={calls} 独立worker数={len(ma._run_workers)}\n")
    fh.write(f"  → {tag} 墙钟均值 {sum(walls)/len(walls):.1f}s\n\n")


if __name__ == "__main__":
    with open(OUT, "w") as fh:
        fh.write("固定计划：3×weather + 1×solo\n\n")
        run_arm(False, "旧:去重+单例", fh)
        run_arm(True, "新:工人池", fh)
    print(open(OUT).read())
