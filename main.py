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

    新增结构化 JSON 输出：/json <schema> <问题> 触发 JSON 模式。
    可用 schema：math / weather / summary。查看可用 /json list。
"""
import os
from dotenv import load_dotenv
from agent.multi_agent import MultiAgent
from agent.json_mode import list_schemas, run_json_mode


def print_help():
    print("""
📖 指令一览：
  直接输入    → 与多 Agent 对话（自动路由）
  /json <schema> <问题> → 结构化 JSON 输出（math/weather/summary）
  /json list  → 查看可用 schema
  /pipe <场景> <问题> → Pipeline 模式（math_to_summary/research_to_report）
  /pipe list  → 查看可用场景
  /trace      → 查看本轮运行轨迹
  /usage      → 查看 token 用量
  /memory     → 查看长期记忆（跨会话）
  /memory_extra → 查看带标签+时间的记忆详情
  /mem_clear  → 清空长期记忆
  /clear      → 清空对话历史（不删长期记忆）
  /exit       → 退出
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
        if low == "/memory_extra":
            print(f"🧠 长期记忆详细（共 {ma.memory.count()} 条，含标签+时间）：")
            for i, item in enumerate(ma.memory.items, 1):
                text = item.get("text", "")
                tags = item.get("meta", {}).get("tags", [])
                type_ = item.get("meta", {}).get("type", "?")
                ts = item.get("meta", {}).get("time", 0)
                import datetime
                tstr = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else "-"
                tag_str = f"tags={tags}" if tags else "no-tags"
                print(f"  {i}. [{tstr}] [{type_}] {tag_str}\n     {text[:80]}")
            continue
        # 【结构化 JSON 模式】 /json list | /json <schema> <问题>
        if user_input.startswith("/json"):
            rest = user_input[len("/json"):].strip()
            if rest == "list" or rest == "":
                print("📐 可用 JSON schema:")
                for name, desc in list_schemas():
                    print(f"  - {name}: {desc}")
                continue
            parts = rest.split(maxsplit=1)
            schema_name = parts[0]
            question = parts[1] if len(parts) > 1 else ""
            if not question:
                print("⚠️ 请提供问题。例如：/json math 帮我算 99 的平方")
                continue
            try:
                # 重置 router（让 JSON 模式不走原来的 Router 委派）
                ma.router.reset()
                result = run_json_mode(ma.router, question, schema_name)
                print(f"\n📋 解析结果：{result}")
            except ValueError as e:
                print(f"⚠️ {e}")
                print("  用 /json list 查看可用 schema")
            continue
        # 【Pipeline 模式】 /pipe list | /pipe <场景> <问题>
        if user_input.startswith("/pipe"):
            rest = user_input[len("/pipe"):].strip()
            if rest == "list" or rest == "":
                print("📦 可用 Pipeline 场景:")
                print("  - math_to_summary : 数学计算 → 一句话总结")
                print("  - research_to_report : 调研 → 报告")
                continue
            parts = rest.split(maxsplit=1)
            scene = parts[0]
            question = parts[1] if len(parts) > 1 else ""
            if not question:
                print("⚠️ 请提供问题。例如：/pipe math_to_summary 99的平方")
                continue
            from agent.pipeline import build_math_to_summary_pipeline, build_research_to_report_pipeline
            try:
                if scene == "math_to_summary":
                    pl = build_math_to_summary_pipeline(ma)
                elif scene == "research_to_report":
                    pl = build_research_to_report_pipeline(ma)
                else:
                    print(f"⚠️ 未知场景: {scene}")
                    print("  用 /pipe list 查看可用场景")
                    continue
                # 重置 router 和专家的 history（让两个 agent 独立对话）
                ma.router.reset()
                for w in ma.experts.values():
                    w.reset()
                state = pl.run(question)
                print("📋 Pipeline 最终状态:")
                for k, v in state.items():
                    if k == "_initial_input":
                        continue
                    print(f"  • {k}: {v}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"⚠️ Pipeline 失败: {e}")
            continue
        ma.run(user_input)


if __name__ == "__main__":
    main()
