# -*- coding: utf-8 -*-
"""预算预警 A/B · 2×2 因素版（2026/10/03）

目的
----
上一版结论：链式任务下预警无效（6/6 硬停，开/关零差异）。
机制猜测：**末步被工具调用占用 → 模型没有"可作答的步"**。

本实验做 2×2，把两个因素**拆开**，检验预警是否真有增量贡献：
    因素 A：REMAINING_STEPS_WARN ∈ {2, 0}
    因素 B：末步撤工具（最后一轮 tool_choice="none"）∈ {off, on}

关键格：WARN=0 + 撤工具 —— 若它也作答，则是"撤工具"救的，与预警无关。

运行
----
    .venv/bin/python docs/experiments/warn_ab_chain_tooloff.py
"""
import os, re, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import agent.core as core
from agent.core import Agent
from docs.experiments.warn_ab_chain import NEXT_TOKEN_SPEC, next_token, TASK, CHAIN

MAX_STEPS = 3
RUNS = int(os.getenv("WARN_AB_RUNS", "3"))


def run_once(warn: int, tool_off: bool):
    core.REMAINING_STEPS_WARN = warn
    a = Agent(system_prompt="你是一个严格的工具执行助手。")
    a.tools_spec.append(NEXT_TOKEN_SPEC)
    a.tool_registry["next_token"] = next_token

    if tool_off:
        _real = a.client.chat.completions.create
        mode = os.getenv("TOOLOFF_MODE", "choice")   # choice | drop
        state = {"n": 0}
        def spy(**kw):
            state["n"] += 1
            if state["n"] >= MAX_STEPS:          # 最后一轮 → 不再给工具
                if mode == "drop":
                    kw["tools"] = None           # 彻底撤掉工具清单
                    kw.pop("tool_choice", None)
                else:
                    kw["tool_choice"] = "none"   # 仅禁止调用
            return _real(**kw)
        a.client.chat.completions.create = spy

    answer = a.run(TASK, max_steps=MAX_STEPS)
    ans = answer or ""
    types = [s.type for s in a.tracer.steps]
    return {
        "warn": warn, "tool_off": tool_off,
        "tool_calls": types.count("tool_call"),
        "answered": "answer" in types,
        "hard_stop": "已超过最大处理轮数" in ans,
        "leak": "DSML" in ans,          # 泄漏：模型在正文里硬撑调工具
        "total_tokens": a.usage["total_tokens"],
        "answer": ans.strip(),
    }


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print(f"令牌链：{CHAIN}   （第5步正解 = {CHAIN[5]}）\n")
    recs = []
    for tool_off in (False, True):
        for warn in (2, 0):
            for i in range(RUNS):
                r = run_once(warn, tool_off)
                recs.append(r)
                print(f"tool_off={str(tool_off):<5} WARN={warn} #{i}  "
                      f"调用={r['tool_calls']}  作答={r['answered']}  "
                      f"硬停={r['hard_stop']}  token={r['total_tokens']}")
    print("\n" + "=" * 82)
    print(f"{'末步撤工具':<12}{'WARN':<6}{'硬停':<8}{'干净收敛':<10}{'DSML泄漏':<10}{'平均token'}")
    print("-" * 82)
    for tool_off in (False, True):
        for warn in (2, 0):
            g = [r for r in recs if r["tool_off"] == tool_off and r["warn"] == warn]
            n = len(g)
            clean = sum(r["answered"] and not r["leak"] for r in g)
            leak = sum(r["leak"] for r in g)
            print(f"{str(tool_off):<12}{warn:<6}"
                  f"{sum(r['hard_stop'] for r in g)}/{n:<6}"
                  f"{clean}/{n:<8}"
                  f"{leak}/{n:<8}"
                  f"{sum(r['total_tokens'] for r in g) / n:.0f}")
    print()
