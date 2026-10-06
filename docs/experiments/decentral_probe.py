# -*- coding: utf-8 -*-
"""去中心化协商专题 · 互评型探针（2026/10/06）

目标：证明集中式（一次性规划 → 并行盲跑 → 汇总）**无法表达「互评」**。

三个梯度：
  P1 轻互评：两位专家给判断 → 必须互相核对 + 指出分歧
  P2 中互评：三位专家独立结论 → 互相挑错 → 各自修订 → 三方共识
  P3 重互评：专家结论**冲突** → 必须协商出统一结论（而非 Merger 硬拼）

观察：
  · _plan 产出什么（会不会把「互评」也一次性规划成盲跑任务？）
  · 互评是否真的发生（专家能否看到彼此输出）
  · 最终答案是「真协商」还是「merger 硬拼/编造」
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.multi_agent import MultiAgent

PROBES = {
    "P1_轻互评": (
        "请让天气专家和数学专家各自独立判断：「今天北京适合户外活动吗？」"
        "（15~28℃ 为适宜）。给出两份判断后，请**两位互相核对**对方的结论，"
        "如果一致就确认，如果不一致就指出分歧点。最后给出核对结果。"
    ),
    "P2_中互评": (
        "请让三位专家（数学、天气、通用）各自独立给出一个结论后，进入**互评环节**："
        "每位专家必须阅读另外两位的结论，指出对方一处问题，并说明自己是否修订结论。"
        "最后汇总三人互评后的共识。"
    ),
    "P3_重互评": (
        "请让天气专家和数学专家分别判断「北京今天热不热」。"
        "如果两人结论不一致，请让他们**通过辩论协商**达成一个统一结论（而不是各说各话）——"
        "谁的理由更充分就采纳谁的。最后只给一个统一结论。"
    ),
}


def probe(name, task):
    print(f"\n{'#'*74}\n# {name}\n{'#'*74}")
    ma = MultiAgent(use_memory=False)
    ma.prefilter = None                      # 强制走 Router
    with contextlib.redirect_stdout(io.StringIO()):
        tasks = ma._plan(task)
    print(f"[_plan 产出] {len(tasks)} 个子任务：")
    for t in tasks:
        print(f"    expert={t['expert']:8s} | {t['subtask'][:72]}")
    # 关键：有没有哪个子任务提到「另一位专家的输出」？
    mentions_other = any(
        any(k in t["subtask"] for k in ["对方", "另外", "互相", "另一位", "前三", "其他专家"])
        for t in tasks
    )
    print(f"[互评依赖是否显式表达] {'✅ 有' if mentions_other else '❌ 无'}")

    with contextlib.redirect_stdout(io.StringIO()):
        ans = ma.run(task)
    print(f"[最终回答]\n{(ans or '').strip()[:520]}")
    # 各 worker 能看到多少
    print(f"[本轮 worker] {[(e, len(w.history)) for e, w in ma._run_workers]}")


if __name__ == "__main__":
    for name, task in PROBES.items():
        probe(name, task)
