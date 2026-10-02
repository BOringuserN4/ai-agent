# -*- coding: utf-8 -*-
"""预算预警 A/B 对照实验（2026/10/03）

目的
----
验证 `core.REMAINING_STEPS_WARN`（剩余步数预警）是否真的让模型**提前收敛**。
昨天（2026/10/02）讲义如实标注：「预警的有效性尚未测出」。

设计
----
- **固定紧预算** `max_steps=3`（唯一能让预警逼近触发的方式）
- **唯一变量** `core.REMAINING_STEPS_WARN ∈ {2(预警开), 0(预警关)}`
  · 关掉的方式是**运行时猴子补丁**，不改源码常量
- 每组跑 RUNS 次，逐跑记录：
  · 实际用了几个 step
  · 是否给出最终结论（vs 撞 max_steps 硬停）
  · 是否说明「缺什么」
  · token 用量

任务
----
必须 ≥6 次工具调用：查 5 个城市天气 + 1 次算平均。
`max_steps=3` 下必然完不成 → 正是「步数紧张」的场景。

运行
----
    .venv/bin/python docs/experiments/warn_ab.py
"""
import os
import re
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

import agent.core as core
from agent.core import Agent

TASK = ("请分别查询北京、上海、广州、深圳、杭州五个城市的当前气温，"
        "然后计算这五个温度的平均值（保留一位小数）。")
MAX_STEPS = 3
RUNS = int(os.getenv("WARN_AB_RUNS", "3"))


def run_once(warn: int, verbose: bool = False):
    """跑一次，返回结构化观察。"""
    # ★ 对照开关：运行时猴子补丁（run() 每轮读模块全局 → 立即生效）
    core.REMAINING_STEPS_WARN = warn

    a = Agent(system_prompt="你是一个善于使用工具的助手。")  # tools=None → 全部
    answer = a.run(TASK, max_steps=MAX_STEPS)
    u = a.usage

    ans_text = answer or ""
    # 撞上限时 core 的返回文案（见 core.py 循环末尾）
    hard_stop = "已超过最大处理轮数" in ans_text
    # 是否明确说缺什么（收敛的信号）
    says_missing = bool(re.search(r"缺|未|无法|只(查|得)到|不足|抱歉|未能", ans_text))

    types = [s.type for s in a.tracer.steps]
    rec = {
        "warn": warn,
        "tool_calls": types.count("tool_call"),
        "answered": "answer" in types,   # 循环内给出过最终回答
        "hard_stop": hard_stop,
        "says_missing": says_missing,
        "prompt_tokens": u["prompt_tokens"],
        "completion_tokens": u["completion_tokens"],
        "total_tokens": u["total_tokens"],
        "answer": ans_text.strip(),
    }
    if verbose:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    return rec


def summarize(records):
    print("\n" + "=" * 60)
    print(f"max_steps={MAX_STEPS}  →  各轮 remaining："
          + ", ".join(str(MAX_STEPS - i) for i in range(MAX_STEPS)))
    print("=" * 60)
    hdr = f"{'组':<8}{'#':<4}{'工具调用':<10}{'给出回答':<10}{'硬停':<8}{'说缺什么':<10}{'total_token':<14}{'回答首行'}"
    print(hdr)
    for i, r in enumerate(records):
        first = (r["answer"].splitlines() or [""])[0][:36]
        print(f"{'WARN=' + str(r['warn']):<8}{i:<4}"
              f"{r['tool_calls']:<10}{str(r['answered']):<10}{str(r['hard_stop']):<8}"
              f"{str(r['says_missing']):<10}"
              f"{r['total_tokens']:<14}{first}")
    print()


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)

    records = []
    for warn in (2, 0):          # 2=预警开（默认）, 0=预警关
        for i in range(RUNS):
            print(f"\n──────── WARN={warn}  第 {i + 1}/{RUNS} 跑 ────────")
            rec = run_once(warn)
            records.append(rec)
    summarize(records)
