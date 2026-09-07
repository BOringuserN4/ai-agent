# -*- coding: utf-8 -*-
"""
main.py — 统一命令行入口（Multi-Agent + 长期记忆）

运行方式：
    python3 main.py

指令：
    直接输入  → 与多 Agent 对话（自动路由到对应专家）
    /trace    → 查看本轮完整轨迹
    /usage    → 查看 token 用量
    /memory   → 查看已沉淀的长期记忆（跨会话保存）
    /mem_clear→ 清空长期记忆
    /clear    → 清空对话历史（不删长期记忆）
    /exit     → 退出

说明：
    本版本已启用长期记忆（RAG）。Agent 会在回答前检索相关历史记忆、回答后沉淀重要信息，
    实现跨会话记住用户信息，且不占用对话上下文窗口。
"""
import os
from dotenv import load_dotenv
from agent.multi_agent import MultiAgent


def print_help():
    print("""
📖 指令一览：
  直接输入  → 与多 Agent 对话（自动路由到对应专家）
  /trace    → 查看本轮运行轨迹
  /usage    → 查看 token 用量
  /memory   → 查看长期记忆（跨会话）
  /mem_clear→ 清空长期记忆
  /clear    → 清空对话历史（不删长期记忆）
  /exit     → 退出
""")


def main():
    load_dotenv()
    if not os.getenv("DEEPSEEK_API_KEY") or len(os.getenv("DEEPSEEK_API_KEY", "")) < 10:
        raise SystemExit("❌ 请在 .env 里配置 DEEPSEEK_API_KEY")

    ma = MultiAgent(use_memory=True)
    print("=" * 50)
    print("🤖 Multi-Agent 已启动（Router + 专家 + 长期记忆）")
    print("  试试：帮我算 123*456  /  上海天气  /  随便聊聊")
    print("  建议先告诉我你的名字或偏好，再重启验证它是否记住")
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
            print("(已清空对话历史，长期记忆保留)")
            continue
        if low == "/help":
            print_help()
            continue
        if low == "/trace":
            ma.print_traces()
            continue
        if low == "/usage":
            total = 0
            for w in ma.experts.values():
                total += w.usage["total_tokens"]
            ma.router.print_usage()
            print(f"📊 全系统累计 tokens：{total}")
            continue
        if low == "/memory":
            print(f"🧠 长期记忆共 {ma.memory.count()} 条：")
            for i, t in enumerate(ma.memory.all_texts(), 1):
                print(f"  {i}. {t}")
            continue
        if low == "/mem_clear":
            ma.memory.clear()
            print("(长期记忆已清空)")
            continue
        ma.run(user_input)


if __name__ == "__main__":
    main()
