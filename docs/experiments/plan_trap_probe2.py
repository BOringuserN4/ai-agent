# -*- coding: utf-8 -*-
"""规划专题 · 陷阱探针 2：更狠的陷阱（2026/10/04）

陷阱 1 失败了（贪心 ReAct 3/3 做对）→ 换两个更苛刻的：

Trap B（全局推理）：找"气温最接近的两座城市" —— 需比较 10 个配对，
        贪心/局部推理容易漏配或算错。
Trap C（长程 + 复用）：6 步流程，结尾要复用开头结果，考验"跨多步保持目标"。
"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TRAPS = {
    "B_最接近两城": (
        "查询北京、上海、广州、深圳、杭州五个城市的当前气温，"
        "然后找出其中**气温最接近的两座城市**（温差绝对值最小），"
        "报告是哪两座城市、温差是多少（保留 1 位小数）。"
    ),
    "C_六步流程": (
        "请严格按顺序完成 6 步：\n"
        "① 获取当前北京时间（记下来，最后要用）；\n"
        "② 查北京气温，记 T1；\n"
        "③ 查上海气温，记 T2；\n"
        "④ 查广州气温，记 T3；\n"
        "⑤ 算出 T1、T2、T3 的平均值 M（保留 1 位小数）；\n"
        "⑥ 最后汇总一句话：现在是北京时间几点几分，T1/T2/T3 分别是多少，平均 M 是多少。"
    ),
}
N = int(os.getenv("TRAP_N", "2"))


def run_trap(name, task):
    print(f"\n{'#'*70}\n# 陷阱 {name}\n{'#'*70}")
    for i in range(1, N + 1):
        print(f"\n──── {name} 第 {i}/{N} 跑 ────")
        a = Agent(system_prompt="你是一个善于使用工具的助手。")
        ans = a.run(task, max_steps=8) or ""
        types = [s.type for s in a.tracer.steps]
        print(f"\n[统计] 工具调用={types.count('tool_call')}  token={a.usage['total_tokens']}")
        print("[回答]", ans.strip()[:220])


if __name__ == "__main__":
    for name, task in TRAPS.items():
        run_trap(name, task)
