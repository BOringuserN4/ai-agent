# -*- coding: utf-8 -*-
"""预算预警 A/B 对照 · 链式任务版（2026/10/03）

为什么要有这一版
----------------
首版（warn_ab.py）任务失败：模型把 6 个 tool_calls **并发塞进 1 步**，
`max_steps=3` 根本不紧 → 预警没机会出手。根因：**一步 ≠ 一次工具调用**。

本版对策：**依赖链**——每个工具调用的入参 = 上一个的输出，
模型**猜不出**（token 是随机的）→ 只能**严格串行**，无法批量。

任务
----
从起始令牌 K7Q 起，连续调用 `next_token` 前进 5 步，报告终点令牌。
→ 结构上必须 **5 步**；`max_steps=3` 下**注定完不成** → 强制造出"步数紧张"。

对照
----
- 固定 `max_steps=3`
- 唯一变量：`core.REMAINING_STEPS_WARN ∈ {2(开), 0(关)}`（运行时猴子补丁）
- 每组 RUNS 次

运行
----
    .venv/bin/python docs/experiments/warn_ab_chain.py
"""
import os
import re
import sys
import json
import random

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import agent.core as core
from agent.core import Agent

# ---- 构造一条"不可预测"的随机令牌链（固定种子 → 可复现）----
_rng = random.Random(20261003)
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
START = "K7Q"
_rest = ["".join(_rng.choice(_ALPHABET) for _ in range(3)) for _ in range(5)]
CHAIN = [START] + _rest          # 长度 6：K7Q → t1 → ... → t5
_NEXT = {CHAIN[i]: CHAIN[i + 1] for i in range(len(CHAIN) - 1)}


def next_token(tok: str) -> str:
    """返回令牌链中 tok 的下一个令牌。"""
    tok = (tok or "").strip().upper()
    return _NEXT.get(tok, "ERR_NOT_FOUND")


NEXT_TOKEN_SPEC = {
    "type": "function",
    "function": {
        "name": "next_token",
        "description": (
            "令牌链推进工具：输入当前令牌，返回链中它的下一个令牌。"
            "链中令牌为不可预测的随机串，无法跳过或预知。"
        ),
        "parameters": {
            "type": "object",
            "properties": {"tok": {"type": "string", "description": "当前令牌"}},
            "required": ["tok"],
        },
    },
}

TASK = (f"链式任务：请调用 next_token 工具，从起始令牌 {START} 开始，"
        f"连续向前推进 5 步（即调用 5 次，每次用上一次的结果作为输入），"
        f"最后告诉我第 5 步得到的令牌是什么。")
MAX_STEPS = 3
RUNS = int(os.getenv("WARN_AB_RUNS", "3"))


def run_once(warn: int, verbose: bool = False):
    core.REMAINING_STEPS_WARN = warn        # ★ 对照开关（运行时猴子补丁）

    a = Agent(system_prompt="你是一个严格的工具执行助手。")
    # 注入实验专用工具（只在本脚本内，不进主项目）
    a.tools_spec.append(NEXT_TOKEN_SPEC)
    a.tool_registry["next_token"] = next_token

    answer = a.run(TASK, max_steps=MAX_STEPS)
    u = a.usage
    ans = answer or ""

    types = [s.type for s in a.tracer.steps]
    # 实际成功推进了几步（链被走了多远）
    called = [s.tool for s in a.tracer.steps if s.type == "tool_call"]
    rec = {
        "warn": warn,
        "tool_calls": types.count("tool_call"),
        "answered": "answer" in types,
        "hard_stop": "已超过最大处理轮数" in ans,
        "says_missing": bool(re.search(r"缺|未|无法|只能|仅|不足|抱歉|未能|没能", ans)),
        "total_tokens": u["total_tokens"],
        "answer": ans.strip(),
    }
    if verbose:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    return rec


def summarize(records):
    print("\n" + "=" * 74)
    print(f"链式任务 · max_steps={MAX_STEPS} · remaining 序列 "
          f"{', '.join(str(MAX_STEPS - i) for i in range(MAX_STEPS))}")
    print("=" * 74)
    print(f"{'组':<8}{'#':<4}{'调用':<6}{'给回答':<8}{'硬停':<8}{'说缺什么':<10}{'token':<8}回答首行")
    for i, r in enumerate(records):
        first = (r["answer"].splitlines() or [""])[0][:30]
        print(f"{'WARN=' + str(r['warn']):<8}{i:<4}{r['tool_calls']:<6}"
              f"{str(r['answered']):<8}{str(r['hard_stop']):<8}"
              f"{str(r['says_missing']):<10}{r['total_tokens']:<8}{first}")
    # 汇总
    print("-" * 74)
    for warn in (2, 0):
        grp = [r for r in records if r["warn"] == warn]
        hard = sum(r["hard_stop"] for r in grp)
        print(f"WARN={warn}: 硬停 {hard}/{len(grp)}  |  平均调用 "
              f"{sum(r['tool_calls'] for r in grp) / len(grp):.1f}  |  平均 token "
              f"{sum(r['total_tokens'] for r in grp) / len(grp):.0f}")
    print()


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print(f"令牌链（调试）：{CHAIN}")
    records = []
    for warn in (2, 0):
        for i in range(RUNS):
            print(f"\n──────── WARN={warn}  第 {i + 1}/{RUNS} 跑 ────────")
            records.append(run_once(warn))
    summarize(records)
