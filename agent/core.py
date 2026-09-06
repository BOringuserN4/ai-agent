# -*- coding: utf-8 -*-
"""
agent/core.py — Agent 核心引擎

职责：
- 管理对话历史（多轮聊天）。
- 把「模型 + 工具声明 + 工具执行」串成 ReAct 循环。
- 封装成简单接口，供上层（如 CLI、未来的可视化界面）调用。

设计原则：
- 工具声明与真实函数都来自 agent.tools，模块化。
- 支持多轮对话：持续把历史追加进 messages。
- ReAct 循环有 max_steps 兜底，防止死循环。
"""
import json
from openai import OpenAI
from dotenv import load_dotenv
from agent.tools import get_tools_spec, get_tool_registry

load_dotenv()


def get_api_key():
    import os
    return os.getenv("DEEPSEEK_API_KEY", "")


class Agent:
    def __init__(self, system_prompt="你是一个乐于助人的 AI 助手。"):
        self.client = OpenAI(
            api_key=get_api_key(),
            base_url="https://api.deepseek.com",
        )
        self.tools_spec = get_tools_spec()
        self.tool_registry = get_tool_registry()
        # 对话历史：开头放系统提示
        self.history = [{"role": "system", "content": system_prompt}]

    def reset(self):
        """清空对话历史，但保留系统提示。"""
        self.history = [self.history[0]]

    def run(self, user_input: str, max_steps=8):
        """处理一轮用户输入，返回最终回复（含可能的工具调用过程日志）。"""
        self.history.append({"role": "user", "content": user_input})
        print(f"\n🧑 用户：{user_input}")

        for _ in range(max_steps):
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=self.history,
                tools=self.tools_spec,
                tool_choice="auto",
                temperature=0.3,
            )
            msg = response.choices[0].message

            # 情况 A：模型没有调用工具 -> 给出最终回答
            if not msg.tool_calls:
                # 把助手回答追加进历史（为了多轮记忆）
                self.history.append({"role": "assistant", "content": msg.content})
                print(f"🤖 助手：{msg.content}")
                return msg.content

            # 情况 B：模型要调用工具
            tool_calls_spec = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            # 记录模型的调用请求（必须，否则工具结果无法对位）
            self.history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": tool_calls_spec,
            })

            # 执行工具，把结果回填
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                fn = self.tool_registry.get(name)
                if fn is None:
                    result = f"❌ 未找到工具: {name}"
                else:
                    result = fn(**args)
                print(f"🛠️  调用 {name}({args}) -> {result}")
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        print("⚠️ 达到最大循环次数，强制结束。")
        return "已超过最大处理轮数。"


def main():
    import os
    if not get_api_key() or len(get_api_key()) < 10:
        raise SystemExit("❌ 请先配置 .env 里的 DEEPSEEK_API_KEY")
    agent = Agent()
    print("🤖 Agent 已启动。输入你的问题，输入 /exit 退出。\n")
    while True:
        try:
            user_input = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit", "退出", "exit"):
            print("再见！")
            break
        agent.run(user_input)


if __name__ == "__main__":
    main()
