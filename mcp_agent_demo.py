# -*- coding: utf-8 -*-
"""
mcp_agent_demo.py — 对照实验：同一任务，「本地工具」vs「MCP 工具」

协议章 · 第四步，2026/09/17。

问的是同一个问题，只换工具来源：

  甲组（本地）：Agent 用 agent/tools.py 里手写的 get_weather
  乙组（MCP） ：Agent 用从 MCP server 动态发现的 get_weather（本地那份被摘掉）

要量出三件事：
  1. 工具 schema 的体积差（描述文本吃 token 的地方）；
  2. 跑同一个问题的总 token；
  3. 墙钟耗时（协议层多出来的往返）。

用法：.venv/bin/python mcp_agent_demo.py
"""
import json
import sys
import time
from pathlib import Path

from agent.core import Agent
from agent.mcp_bridge import build_weather_bridge, attach_mcp_tools

REPO_ROOT = str(Path(__file__).resolve().parent)
QUESTION = "杭州现在天气怎么样？"
SYSTEM = "你是一个助手。需要实时信息时必须调用工具，拿到工具结果后再回答，不要凭记忆编造。"
# 每组跑这么多次：单次耗时抖动大，多跑几次取平均才敢下结论
REPEATS = 3


def _reset_usage(agent):
    agent.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _measure(make_agent, label):
    """跑 REPEATS 次，返回 schema 体积 / 各次 token / 平均耗时 / 答案。"""
    a = make_agent()
    spec_chars = len(json.dumps(a.tools_spec, ensure_ascii=False))
    names = [s["function"]["name"] for s in a.tools_spec]
    print(f"🔧 工具集（{len(names)} 个）：{names}")
    print(f"📏 schema 体积：{spec_chars} 字符")

    tokens, elapsed, last_answer, used = [], [], "", []
    for i in range(REPEATS):
        _reset_usage(a)
        a.reset()
        t0 = time.time()
        last_answer = a.run(QUESTION)
        elapsed.append(time.time() - t0)
        tokens.append(a.usage["total_tokens"])
        used = [s.tool for s in a.tracer.steps if s.type == "tool_call"]
        print(f"   第 {i+1} 次：{tokens[-1]} token，{elapsed[-1]:.2f}s")
    return {"answer": last_answer, "spec_chars": spec_chars, "tools": names,
            "tokens": tokens, "avg_tokens": round(sum(tokens) / len(tokens)),
            "avg_elapsed": round(sum(elapsed) / len(elapsed), 2),
            "tools_used": used}


def run_local():
    print("\n" + "#" * 60)
    print("# 甲组 · 本地工具（agent/tools.py 手写声明）")
    print("#" * 60)
    # 只留 get_weather：与乙组工具集严格对齐，token 差才归因得到「协议」
    return _measure(lambda: Agent(system_prompt=SYSTEM, tools=("get_weather",)), "本地")


def run_mcp(bridge):
    print("\n" + "#" * 60)
    print("# 乙组 · MCP 工具（从 server 动态发现）")
    print("#" * 60)

    def make():
        a = Agent(system_prompt=SYSTEM, tools=None)
        # 关键：清空本地工具，让天气能力**只能**来自 MCP —— 工具集与甲组严格一致
        a.tools_spec = []
        a.tool_registry = {}
        attach_mcp_tools(a, bridge)
        return a

    return _measure(make, "MCP")


def main():
    local = run_local()

    bridge = build_weather_bridge(REPO_ROOT)
    print("\n🔌 启动 MCP bridge…")
    bridge.start()
    try:
        mcp = run_mcp(bridge)
    finally:
        bridge.stop()

    print("\n" + "=" * 64)
    print("📊 对照结论")
    print("=" * 64)
    print(f"{'组别':<14}{'来源':<10}{'schema字符':>10}{'平均token':>10}{'平均耗时':>10}")
    print("-" * 64)
    print(f"{'甲组 · 本地':<14}{'手写声明':<10}{local['spec_chars']:>10}"
          f"{local['avg_tokens']:>10}{str(local['avg_elapsed']) + 's':>10}")
    print(f"{'乙组 · MCP':<14}{'动态发现':<10}{mcp['spec_chars']:>10}"
          f"{mcp['avg_tokens']:>10}{str(mcp['avg_elapsed']) + 's':>10}")
    print("-" * 64)

    ds = mcp["spec_chars"] - local["spec_chars"]
    dt = mcp["avg_tokens"] - local["avg_tokens"]
    de = round(mcp["avg_elapsed"] - local["avg_elapsed"], 2)
    print(f"schema 字符差：{ds:+d}")
    print(f"平均 token 差：{dt:+d}")
    print(f"平均耗时差：{de:+}s")
    print(f"\n（各次 token：甲组 {local['tokens']}；乙组 {mcp['tokens']}）")
    print("\n两组答案：")
    print(f"  甲组：{local['answer'][:100]}")
    print(f"  乙组：{mcp['answer'][:100]}")
    print(f"\n实际调用的工具：甲组 {local['tools_used']}  乙组 {mcp['tools_used']}")
    print("\n💡 结论：MCP 没让 token 变便宜（描述文本还要多花一点），"
          "它买的是「一次实现、处处可用」——代价是协议层的一次跨进程往返。")


if __name__ == "__main__":
    main()
