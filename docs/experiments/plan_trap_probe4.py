# -*- coding: utf-8 -*-
"""规划专题 · 陷阱探针 4：规模（多条目易漏）（2026/10/04）

前四陷阱全对 → 病未现。本探针加"条目数"，打贪心的漏项软肋：
  6 城 × (气温 + 当地时间) = 12 个数据点，需全给，一个不漏。
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都"]
TASK = (
    "请查询以下 6 个城市的**当前气温**和**当地时间**："
    "北京、上海、广州、深圳、杭州、成都。\n"
    "输出一个表格，每城一行，列为：城市 | 气温 | 当地时间。6 城一个都不能少。"
)
N = int(os.getenv("TRAP_N", "3"))


if __name__ == "__main__":
    for i in range(1, N + 1):
        a = Agent(system_prompt="你是一个善于使用工具的助手。")
        ans = a.run(TASK, max_steps=8) or ""
        t = [s.type for s in a.tracer.steps]
        missing = [c for c in CITIES if c not in ans]
        print(f"跑{i}: 工具调用={t.count('tool_call')} token={a.usage['total_tokens']} "
              f"缺失城市={missing or '无'} {'✅' if not missing else '❌'}")
