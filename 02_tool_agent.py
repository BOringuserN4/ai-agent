# -*- coding: utf-8 -*-
"""
02_tool_agent.py — 带工具调用 + ReAct 循环的 Agent

这是 Agent 真正「活过来」的一步：
Agent 会先「思考 -> 决定要不要用工具 -> 用工具拿结果 -> 观察结果 -> 再思考」，
循环往复，直到完成任务。这个循环就是 ReAct（Reason + Act）。

运行方式：
    python3 02_tool_agent.py
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if not api_key or len(api_key) < 10:
    raise SystemExit("❌ 请在 .env 里填入你的 DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

# ============================================================
# 第一步：定义工具（Tool）。这是 Agent 的「手和脚」。
# 我们用 DeepSeek 支持的 function calling 规范来声明一个计算器。
# ============================================================
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "做四则运算的简易计算器。当用户需要算数学表达式的值时可调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的数学表达式，例如 '12 * (5 + 3)' 或 '2 ** 10'",
                    }
                },
                "required": ["expression"],
            },
        },
    }
]

# ============================================================
# 第二步：实现工具的真实逻辑（这是 Python 真正的执行体）
# ============================================================
def run_calculator(expression: str) -> str:
    """真正执行计算。这里用 eval 做演示（个人项目可用，生产勿用！）。"""
    allowed = set("0123456789+-*/().% ")
    if any(ch not in allowed for ch in expression):
        return "❌ 表达式包含非法字符"
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"❌ 计算出错: {e}"

# 把「函数名 -> 真实函数」映射起来，Agent 说要用哪个，我们就调哪个
TOOL_REGISTRY = {
    "calculator": run_calculator,
}

# ============================================================
# 第三步：ReAct 主循环
# 大模型是「大脑」，它不会真的算，而是「决定调用 calculator 并把参数写好」。
# 我们解析它的调用请求 -> 真的执行 -> 把结果塞回上下文 -> 再让模型继续。
# ============================================================
def run_agent(user_input: str, max_steps=5):
    messages = [
        {"role": "system", "content": "你是一个能调用工具的助手。需要用计算器时，调用 calculator 工具；算完后再用一句话告诉用户结果。"},
        {"role": "user", "content": user_input},
    ]
    print(f"\n🧑 用户：{user_input}")

    for step in range(max_steps):
        # 让大模型「思考」：它要么返回文字，要么请求调用工具
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,               # 告诉模型「你有这些工具可用」
            tool_choice="auto",         # 让模型自己决定要不要用
            temperature=0.3,
        )
        msg = response.choices[0].message

        # 情况 A：模型没有要求调用工具 -> 直接给出最终回答，结束循环
        if not msg.tool_calls:
            print(f"🤖 助手：{msg.content}")
            return msg.content

        # 情况 B：模型要求调用工具 -> 我们真的要执行它
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })
        # 逐个执行工具，把结果作为 tool 角色回填
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = TOOL_REGISTRY[name](**args)
            print(f"🛠️  调用 {name}({args}) -> {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    print("⚠️ 达到最大循环次数，强制结束。")
    return messages[-1].get("content", "")


# ============================================================
# 第 4 步：跑一个例子
# ============================================================
if __name__ == "__main__":
    run_agent("帮我算一下 (88 + 12) * 5 等于多少？")
