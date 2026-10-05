# -*- coding: utf-8 -*-
"""编排必要性论证（2026/10/05）—— 慢工具下，工人池/并行是否必要

关键细节：core.run() 里工具执行是 `for tc in msg.tool_calls:` —— **批在同一步的
多个工具调用是顺序执行的**。所以：
  · 快工具：批量=几乎免费 → 单 worker 够（上一实验结论）
  · 慢工具：批量=顺序累加 → 单 worker 慢，并行才救得回（本实验）

对照（同一任务、同一工具，只变「单 worker vs 工人池」）：
  · 单 worker（合并）：1 个 worker 处理 N 城市 → N 个慢调用顺序执行
  · 工人池：N 个 worker 各处理 1 城市 → 并行

工具：slow_lookup(city) = sleep(SLOW 秒) + 返回一个值。
"""
import os, sys, time, io, contextlib
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

SLOW = float(os.getenv("SLOW_SEC", "3"))
CITIES = ["北京", "上海", "广州"]
N = int(os.getenv("NEC_N", "3"))   # 每档跑几次取均值

SLOW_SPEC = {"type": "function", "function": {
    "name": "slow_lookup",
    "description": "查询某城市的指标值（每次查询需要几秒，属慢操作）。",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}


def slow_lookup(city: str) -> str:
    time.sleep(SLOW)
    return f"{city}: 20.5"


def make_worker():
    a = Agent(system_prompt="你是严格的工具执行助手。")
    a.tools_spec.append(SLOW_SPEC)
    a.tool_registry["slow_lookup"] = slow_lookup
    return a


def single_worker(cities):
    """单 worker 处理全部城市（模拟「合并」：同域子任务合给 1 个 worker）。"""
    a = make_worker()
    q = "请分别查询 " + "、".join(cities) + " 的 slow_lookup 值，并汇总。"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # 主线程统一重定向（避免线程内重定向踩踏）
        t0 = time.time()
        ans = a.run(q, max_steps=8)
        return round(time.time() - t0, 2), ans


def worker_pool(cities):
    """工人池：每城市 1 个独立 worker，并行。"""
    def one(city):
        a = make_worker()
        return a.run(f"请查询 {city} 的 slow_lookup 值。", max_steps=6)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):      # 主线程统一重定向
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=len(cities)) as pool:
            list(pool.map(one, cities))
        return round(time.time() - t0, 2)


if __name__ == "__main__":
    import statistics
    print(f"慢工具 sleep={SLOW}s，城市数={len(CITIES)}\n")
    for label, fn in [
        ("单worker(合并)", lambda: single_worker(CITIES)[0]),
        ("工人池(N并行)", lambda: worker_pool(CITIES)),
    ]:
        ws = [fn() for _ in range(N)]
        print(f"{label:<16} 墙钟={ws}  均值={statistics.mean(ws):.1f}s")
    # 理论：顺序 N×SLOW=%.1fs；并行≈SLOW=%.1fs
    print(f"\n理论参照：顺序 {len(CITIES)}×{SLOW}={len(CITIES)*SLOW:.0f}s ；并行 ≈{SLOW:.0f}s（+LLM开销）")
