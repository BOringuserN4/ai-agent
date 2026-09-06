# -*- coding: utf-8 -*-
"""
04_cli_dashboard.py — 命令行入口（第4步：带追踪/用量）

比 03 多了洞察能力：
  /trace  → 查看本轮 Agent 的运行轨迹（每一步干了啥）
  /usage  → 查看本轮 token 用量（成本）

运行方式：
    python3 04_cli_dashboard.py
"""
from agent import Agent


def print_help():
    print("""
📖 指令一览：
  直接输入  → 和 Agent 对话
  /trace    → 查看本轮运行轨迹
  /usage    → 查看本轮 token 用量
  /clear    → 清空对话历史
  /exit     → 退出
""")


def main():
    agent = Agent()
    print("=" * 50)
    print("🤖 AI Agent 已启动（带追踪版）")
    print("  支持：计算器 / 时间 / 天气 / 自由对话")
    print("  输入 /help 查看指令")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            continue
        low = user_input.lower()
        if low in ("/exit", "/quit", "退出", "exit"):
            print("再见！")
            break
        if low in ("/clear", "清空"):
            agent.reset()
            print("(已清空对话历史)")
            continue
        if low == "/help":
            print_help()
            continue
        if low == "/trace":
            agent.print_trace()
            continue
        if low == "/usage":
            agent.print_usage()
            continue
        agent.run(user_input, max_tokens=6000)
        # 自动展示本轮轨迹和用量
        agent.print_trace()
        agent.print_usage()


if __name__ == "__main__":
    main()
