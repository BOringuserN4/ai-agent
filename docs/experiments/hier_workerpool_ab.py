# -*- coding: utf-8 -*-
"""工人池 A/B 对照 v2（2026/10/05）—— 强制走 Router，排除预筛干扰

对照「同域多子任务」：
  · 旧（ALLOW_PARALLEL_SAME_ROLE=False）：按 expert 去重 + 共享单例 → 串行
  · 新（True）：同域多子任务 + 每子任务独立 worker → 真并行
指标：_plan 子任务数、墙钟、各 worker 工具调用、结果完整性。
"""
import os, sys, time, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
import agent.multi_agent as mam
from agent.multi_agent import MultiAgent

TASK = ("请分头调研北京、上海、广州三个城市，每个城市都要给出当前气温，"
        "并判断该城市此刻是否适合户外活动（气温 15~28℃ 为适宜）。最后给出三城对比结论。")
CITIES = ["北京", "上海", "广州"]
N = int(os.getenv("AB_N", "3"))
OUT = os.path.join(ROOT, "tmp-artifacts", "workerpool_ab.txt")


def run_arm(flag, tag, fh):
    mam.ALLOW_PARALLEL_SAME_ROLE = flag
    rows = []
    for i in range(N):
        ma = MultiAgent(use_memory=False)
        ma.prefilter = None            # ← 强制走 Router，排除预筛干扰
        with contextlib.redirect_stdout(io.StringIO()):
            ts = ma._plan(TASK)
            n_weather = sum(1 for t in ts if t["expert"] == "weather")
            t0 = time.time()
            ans = ma.run(TASK)
            wall = round(time.time() - t0, 2)
        calls = {}
        for name, w in ma._run_workers:
            c = sum(1 for s in w.tracer.steps if s.type == "tool_call")
            calls[name] = calls.get(name, 0) + c
        ok = all(c in (ans or "") for c in CITIES)
        rows.append((len(ts), n_weather, wall, calls, ok))
        fh.write(f"[{tag}] 跑{i+1}: _plan={len(ts)}任务(weather={n_weather}) "
                 f"墙钟={wall}s 工具调用={calls} 完整={ok}\n")
    ws = [r[2] for r in rows]
    fh.write(f"  → {tag} 墙钟均值 {sum(ws)/len(ws):.1f}s  子任务均值 "
             f"{sum(r[0] for r in rows)/len(rows):.1f}  完整 {sum(r[4] for r in rows)}/{len(rows)}\n\n")


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("任务：3 城分头调研（强制走 Router）\n\n")
        run_arm(False, "旧:去重+单例", fh)
        run_arm(True, "新:工人池", fh)
    print(open(OUT).read())
