# -*- coding: utf-8 -*-
"""
03_cli_chat.py — 命令行交互入口

这是日常用来「跟 Agent 聊天」的入口。它支持多轮对话（记住上下文），
Agent 现在具备真实工具：计算器、时间、查天气。

运行方式：
    python3 03_cli_chat.py
"""
from agent import Agent


def main():
    agent = Agent()
    print("=" * 50)
    print("🤖 AI Agent 已启动（命令行版）")
    print("  支持：计算器、当前时间、查询天气、自由对话")
    print("  指令：/exit  退出 | /clear  清空历史")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit", "退出", "exit"):
            print("再见！")
            break
        if user_input.lower() in ("/clear", "清空"):
            agent.reset()
            print("(已清空对话历史)")
            continue
        agent.run(user_input)


if __name__ == "__main__":
    main()
