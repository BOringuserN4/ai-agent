# -*- coding: utf-8 -*-
"""
eval_fanout_parallel.py — 真并行 Fan-out 对照实验（2026/09/20）

目的：量出「并行」到底省了多少墙钟时间，以及代价是什么。

=== 实验设计（关键）===

**不经过 Router**，直接构造 2 个子任务喂给 fan-out。
理由：Router 现在倾向判「不拆」（四条判据很严），如果让它决定，
很可能根本进不到并行路径，实验就测不到东西。
更要紧的是——**对照实验必须只变一个变量**：这里要测的是「串行 vs 并行」，
所以要把「Router 怎么判」这个变量固定住（直接给同样的子任务）。

=== 两个指标 ===

1. **墙钟时间**（本次的核心指标）：串行 = 各任务之和；并行 ≈ max(各任务) + 调度开销
2. **token**：应该**几乎不变**——并行不改变工作量，只改变发生时间。
   如果 token 变了，说明改错了（多跑或少跑了东西）。

用法：.venv/bin/python eval_fanout_parallel.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.multi_agent import MultiAgent

# 刻意选两个「互相独立、都要调 LLM」的子任务：
#   - 数学：要调 calculator 工具 + 一轮 LLM
#   - 天气：要调 get_weather 工具 + 一轮 LLM
# 两者无依赖 → 满足并行的前提
SUBTASKS = [
    {"expert": "math",    "subtask": "帮我算 123*456 等于多少"},
    {"expert": "weather", "subtask": "上海现在天气怎么样"},
]

REPEATS = 3


def _zero_usage(ma):
    for w in ma.experts.values():
        w.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    ma.router.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    ma.merger.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _total_tokens(ma):
    return (sum(w.usage["total_tokens"] for w in ma.experts.values())
            + ma.router.usage["total_tokens"] + ma.merger.usage["total_tokens"])


def run_serial(ma):
    """串行：逐个跑（改造前的行为）。"""
    parts = []
    for t in SUBTASKS:
        expert, subtask = t["expert"], t["subtask"]
        worker = ma.experts[expert]
        worker.reset()
        t0 = time.time()
        ans = worker.run_traced(subtask, trace_name=f"expert-{expert}", user_id="demo")
        parts.append((expert, subtask, ans, round(time.time() - t0, 2)))
    return parts


def run_parallel(ma):
    """并行：走新写的 _fanout_parallel。"""
    return ma._fanout_parallel(SUBTASKS)


def main():
    print("=" * 72)
    print("🔬 真并行 Fan-out 对照实验")
    print("=" * 72)
    print(f"子任务：{[t['expert'] for t in SUBTASKS]}")
    print("（不经 Router，直接喂子任务——保证只变「串行/并行」这一个变量）\n")

    results = {}

    for mode, fn in (("串行", run_serial), ("并行", run_parallel)):
        print("\n" + "#" * 72)
        print(f"# {mode}")
        print("#" * 72)
        walls, tokens, per_task = [], [], []
        for i in range(REPEATS):
            # 注意：MultiAgent 构造（建专家、建 LLM client）**不计入计时**——
            # 它约 0.6s 且两种模式都要付，留在里面会稀释真实差异。
            ma = MultiAgent(use_memory=False)   # 关记忆，避免额外变量
            _zero_usage(ma)
            t0 = time.time()
            parts = fn(ma)
            wall = time.time() - t0
            walls.append(wall)
            tokens.append(_total_tokens(ma))
            per_task = [p[3] for p in parts]
            print(f"  第 {i+1} 次：墙钟 {wall:.2f}s｜token {tokens[-1]}"
                  f"｜各任务 {per_task}")
        results[mode] = {
            "wall": sum(walls) / len(walls),
            "token": sum(tokens) / len(tokens),
            "per_task": per_task,
        }

    print("\n" + "=" * 72)
    print("📊 对照结论")
    print("=" * 72)
    s, p = results["串行"], results["并行"]
    print(f"{'模式':<8}{'平均墙钟':>12}{'平均 token':>14}{'各任务耗时':>26}")
    print("-" * 72)
    print(f"{'串行':<8}{s['wall']:>10.2f}s{s['token']:>14.0f}"
          f"{str(s['per_task']):>26}")
    print(f"{'并行':<8}{p['wall']:>10.2f}s{p['token']:>14.0f}"
          f"{str(p['per_task']):>26}")
    print("-" * 72)

    saved = s["wall"] - p["wall"]
    ideal = s["wall"] - max(s["per_task"])
    overhead = p["wall"] - max(p["per_task"])
    print(f"\n墙钟节省：{saved:+.2f}s（{saved / max(s['wall'], 1e-9) * 100:+.0f}%）")
    print(f"理论最优：省到 {max(s['per_task']):.2f}s（即最长任务的时间）")
    print(f"→ 实际 {p['wall']:.2f}s vs 理论 {max(p['per_task']):.2f}s"
          f"，差 {overhead:+.2f}s = **调度开销**")
    print(f"\ntoken 变化：{s['token']:.0f} → {p['token']:.0f}"
          f"（{p['token'] - s['token']:+.0f}）")
    print("  → token 应几乎不变（并行不改工作量）。若明显变化 = 改错了。")

    infl = [p["per_task"][i] - s["per_task"][i]
            for i in range(min(len(p["per_task"]), len(s["per_task"])))]
    print(f"\n各任务「并行 vs 串行」耗时差：{infl}")
    print("  → 若为正，说明并行时**单个任务也变慢了**：")
    print("     可能是云端对并发请求排队，或本机线程/GIL 争抢。")
    print("     这是并行的隐性成本——不只付调度费，单任务也可能变慢。")

    print("\n怎么读：")
    print("  · 省的时间 ≈ 「较短任务」的全程 —— 它被藏到了较长任务的背后")
    print("  · 调度开销就是「并行墙钟 − 最长任务」，这才是并行的真实成本")
    print("  · 任务越短、开销占比越大，并行的收益越小（极端情况会倒亏）")


if __name__ == "__main__":
    main()
