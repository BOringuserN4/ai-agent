# -*- coding: utf-8 -*-
"""
minimal.py — 阶梯 0：最小可运行的 Agent（约 120 行）

=== 这个文件是干什么的 ===

把 Agent 剥到只剩「本质」，让你**一口气读完就懂**。

读完它你会明白：Agent = 一个循环 + 一份工具清单。
其它所有东西（记忆 / 编排 / 评测 / 可观测）都是**在它之上加出来的**。

=== 对照：本项目的能力阶梯 ===

  阶梯 0 · 最小 Agent      ← 本文件（约 120 行）
      纯 ReAct 循环 + 2 个纯本地工具。无记忆、无编排、无埋点。
  阶梯 1 · + 记忆          见 agent/memory.py（短期历史 + 长期向量记忆）
  阶梯 2 · + 工具生态      见 agent/tools.py + agent/mcp_bridge.py（MCP）
  阶梯 3 · + 编排          见 agent/multi_agent.py（Router / Fan-out / Pipeline / Evaluator-Critic）
  阶梯 4 · + 评测与可观测  见 agent/judge.py + eval_runner.py + Langfuse 埋点

  每一级都是**独立可跑**的，不是片段。本文件是最下面那一级。

=== 它和完整版（agent/core.py）的差别 ===

完整版 385 行，多出来的部分**每一处都有理由**（记忆注入、上下文预算、
轨迹记录、埋点、错误处理……）。但对**第一次读**的人来说，那些都是噪声。
所以先读这个，再读那个。

运行：
    .venv/bin/python minimal.py "帮我算 123 * 456"
    .venv/bin/python minimal.py            # 进入交互模式
"""
import datetime
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# ---------------------------------------------------------------
# 1) 工具：定义 + 实现 + 注册表
#
#    Agent 的「手」就这三样东西。三者的名字必须一致，否则调不到。
# ---------------------------------------------------------------

def calculator(expression: str) -> str:
    """四则运算。"""
    allowed = set("0123456789+-*/().% ")
    if any(ch not in allowed for ch in expression):
        return "❌ 表达式含非法字符"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"❌ 计算出错: {e}"


def current_time(tz: str = "Asia/Shanghai") -> str:
    """当前时间。"""
    try:
        now = datetime.datetime.now(ZoneInfo(tz))
    except Exception:
        return "❌ 未知时区"
    return now.strftime("%Y-%m-%d %H:%M:%S")


# ① 给模型看的「工具说明书」（OpenAI Function Calling 格式）
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算数学表达式，如 '12 * (5 + 3)'。",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "获取指定时区的当前时间。",
            "parameters": {
                "type": "object",
                "properties": {"tz": {"type": "string", "description": "时区名，如 Asia/Shanghai"}},
            },
        },
    },
]

# ② 真正执行的函数（名 -> 函数）
TOOL_FUNCTIONS = {"calculator": calculator, "current_time": current_time}


# ---------------------------------------------------------------
# 2) ReAct 循环 —— Agent 的全部本质都在这里
# ---------------------------------------------------------------

SYSTEM_PROMPT = "你是一个助手。需要计算或查时间时必须调用工具，不要心算或编造。"


def run_agent(user_input, client, model, max_steps=8, verbose=True):
    """一个完整的 Agent：问到答案为止。

    循环的每一步只做三件事：
      ① 把「历史」发给模型
      ② 模型要么给答案（结束），要么要调工具（执行后把结果塞回历史）
      ③ 回到 ①
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    for step in range(1, max_steps + 1):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS_SPEC, temperature=0.3,
        )
        msg = resp.choices[0].message
        messages.append(msg)          # 模型这轮的输出也要进历史

        # 【出口】模型没要工具 → 它认为任务完成了
        if not msg.tool_calls:
            return msg.content

        # 【执行】模型要调工具 → 逐个跑，把结果塞回历史
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            fn = TOOL_FUNCTIONS.get(name)
            if verbose:
                print(f"  🛠️  {name}({args})")
            result = fn(**args) if fn else f"❌ 未知工具: {name}"
            if verbose:
                print(f"      → {result}")
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": str(result),
            })
        # 循环继续：把带上工具结果的历史再发给模型

    return "⚠️ 达到最大步数仍未收敛"


# ---------------------------------------------------------------
# 3) 入口
# ---------------------------------------------------------------

def main():
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if len(key) < 10:
        raise SystemExit("❌ 请先在 .env 配置 DEEPSEEK_API_KEY")

    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    model = "deepseek-flash"

    if len(sys.argv) > 1:                      # 单次执行
        print(run_agent(" ".join(sys.argv[1:]), client, model))
        return

    print("🤖 最小 Agent（输入 /exit 退出）")   # 交互模式
    while True:
        try:
            q = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in ("/exit", "/quit", "exit"):
            break
        if not q:
            continue
        t0 = time.time()
        print(f"🤖 {run_agent(q, client, model)}")
        print(f"   （{time.time() - t0:.1f}s）")


if __name__ == "__main__":
    main()
