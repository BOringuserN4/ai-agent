# -*- coding: utf-8 -*-
"""
main.py — 统一命令行入口（Multi-Agent）

这是重构后的唯一入口，替代原先教学式的 01~04 分散文件。
直接运行即进入「多专家协作」的命令行交互。

运行方式：
    python3 main.py

指令：
    直接输入  → 与多 Agent 对话（自动路由到对应专家）
    /trace    → 查看本轮完整轨迹（每步思考/调用/结果）
    /usage    → 查看 token 用量
    /clear    → 清空对话历史
    /exit     → 退出
"""
import os
from agent.multi_agent import MultiAgent

# 为 /trace 需要：MultiAgent 已内置每步轨迹
def print_help():
    print("""
📖 指令一览：
  直接输入  → 与多 Agent 对话（自动路由到对应专家）
  /trace    → 查看本轮运行轨迹
  /usage    → 查看 token 用量
  /clear    → 清空对话历史
  /exit     → 退出
""")


def main():
    # 校验 API key
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("DEEPSEEK_API_KEY") or len(os.getenv("DEEPSEEK_API_KEY", "")) < 10:
        raise SystemExit("❌ 请在 .env 里配置 DEEPSEEK_API_KEY")

    ma = MultiAgent()
    print("=" * 50)
    print("🤖 Multi-Agent 已启动（Router + 专家）")
    print("  试试：帮我算 123*456  /  上海天气  /  随便聊聊")
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
            ma.router.reset()
            for w in ma.experts.values():
                w.reset()
            print("(已清空对话历史)")
            continue
        if low == "/help":
            print_help()
            continue
        if low == "/trace":
            ma.print_traces()
            continue
        if low == "/usage":
            # 汇总所有 experts 的用量
            total = 0
            for w in ma.experts.values():
                total += w.usage["total_tokens"]
            ma.router.print_usage()
            print(f"📊 全系统累计 tokens：{total}")
            continue
        ma.run(user_input)


if __name__ == "__main__":
    main()
