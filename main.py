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

    新增 Evaluator-Critic 模式（2026/09/16）：/ec <任务> 触发「生成→批判→重做」循环。

    新增 Group Chat 模式（2026/10/06）：/gc <议题> 触发去中心化协商（共享频道轮转 + 主持收敛）。

    新增 Contract Net 模式（2026/10/07）：/cn <任务> 触发任务发标-投标-中标（竞价择优分配）。

    新增 Debate 模式（2026/10/08）：/debate <议题> 触发正反辩论（结构化对抗 + 裁决）。
"""
import os
from dotenv import load_dotenv
from agent.multi_agent import MultiAgent
from agent.json_mode import list_schemas, run_json_mode


# ---- Debate 内置演示（正反围绕一个争议议题辩论）----
def _debate_panel(topic):
    """默认正反双方就议题辩论，再裁决。"""
    from agent.debate import Debate
    d = Debate(topic=topic, rounds=1)
    d.add_side("正方", "你是**正方**。尽力论证该议题的“赞成”一面，反驳对方。")
    d.add_side("反方", "你是**反方**。尽力论证该议题的“反对”一面，找出对方的致命问题。")
    d.run()
    print(f"\n📊 本轮成本：{d.report()['total_tokens']} tokens（≈ 角色数 × 轮数 倍）")
    return d


# ---- Contract Net 内置演示（候选人各持私有信息，中央无法区分）----
def _cn_demo():
    """内置案例：三位工程师各持私有信息，中央靠简介无法区分谁最合适。"""
    from agent.contract_net import ContractNet
    cn = ContractNet()
    cn.add_bidder("甲", "你是工程师「甲」。你的私有信息：你精通 Flink，当前无其他任务，预估 1 天可定位修复。")
    cn.add_bidder("乙", "你是工程师「乙」。你的私有信息：你不熟 Flink（只做过 Spark），手头有两个 deadline 今晚到期，预估至少 5 天。")
    cn.add_bidder("丙", "你是工程师「丙」。你的私有信息：你懂一点 Flink 但不深，正在休假中（明天起三天不在），预估 3 天且需远程。")
    briefs = {n: f"{n}：数据平台工程师，工龄 4 年，参与过若干数据项目。" for n in ["甲", "乙", "丙"]}
    r = cn.run("公司有一台 Flink 实时管道的消费延迟异常（积压 ~2 小时），需要一位工程师接手排查并修复。",
               briefs=briefs)
    print(f"\n📊 本轮成本：{r['total_tokens']} tokens（报价臂 ≈ 集中式的 5×）")
    return r


# ---- Group Chat 内置演示（含分散的私有信息，验证「信息汇集」价值）----
def _gc_demo():
    """跑内置案例：信息分散在两位参与者手中，集中式只能猜，Group Chat 能汇集。"""
    from agent.group_chat import GroupChat
    gc = GroupChat(max_rounds=1)
    gc.add_participant(
        "库存",
        "你是库存系统负责人。你的私有信息：西仓有现货可立即出库；东仓无现货（补货最快 5 天）。"
        "只陈述与决策相关的事实，简短。", tools=())
    gc.add_participant(
        "风控",
        "你是风控负责人。你的私有信息：西仓所在区域今日有强降雨预警，出库装车可能延误 1–2 天；"
        "东仓无此问题。只陈述与决策相关的事实，简短。", tools=())
    final = gc.run("订单 #A100 应从哪里发货？必须二选一：东仓 / 西仓。最后一行只写：答案=<选项>")
    print("\n📊 本轮成本：", gc.report()["total_tokens"], "tokens")
    return final


def _gc_panel(topic):
    """无私有信息时，退化为「支持 / 反对 / 中立」三角色小组。"""
    from agent.group_chat import GroupChat
    gc = GroupChat(max_rounds=2)
    gc.add_participant("支持方", "你是支持方。尽力论证该提议的可行性与收益，可质疑反对意见。", tools=())
    gc.add_participant("反对方", "你是反对方。尽力找出该提议的风险与漏洞，可质疑支持意见。", tools=())
    gc.add_participant("中立分析", "你是中立分析者。指出双方论证中的证据缺口，不站队。", tools=())
    final = gc.run(topic)
    print("\n📊 本轮成本：", gc.report()["total_tokens"], "tokens")
    return final


def print_help():
    print("""
📖 指令一览：
  直接输入    → 与多 Agent 对话（自动路由）
  /json <schema> <问题> → 结构化 JSON 输出（math/weather/summary）
  /json list  → 查看可用 schema
  /pipe <场景> <问题> → Pipeline 模式（math_to_summary/research_to_report）
  /pipe list  → 查看可用场景
  /ec <任务>   → Evaluator-Critic（生成→批判→不达标重做）
  /ec demo    → 跑内置正例（硬约束文案，能挑错也能改好）
  /ec bad     → 跑内置反例（缺信息，命中否决线④，白烧 token）
  /ec list    → 查看可用示例
  /gc <议题>   → Group Chat 去中心化协商（共享频道轮转 + 主持收敛）
  /gc demo    → 内置案例：信息分散在参与者手中（集中式只能猜）
  /gc list    → 查看 Group Chat 用法说明
  /cn <任务>   → Contract Net 任务发标-投标-中标（竞价择优分配）
  /cn demo    → 内置案例：三位工程师各持私有信息（中央无法区分）
  /cn list    → 查看 Contract Net 用法说明
  /debate <议题> → Debate 正反辩论（结构化对抗 + 裁决）
  /debate list   → 查看 Debate 用法说明
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
            from agent.pipeline import (
                build_math_to_summary_pipeline,
                build_research_to_report_pipeline,
            )
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
        # 【Evaluator-Critic 模式】 /ec demo | /ec bad | /ec <任务>
        if user_input.startswith("/ec"):
            from agent.evaluator_critic import (
                EvaluatorCritic, POSITIVE_TASK, NEGATIVE_TASK,
            )
            rest = user_input[len("/ec"):].strip()
            if rest == "list" or rest == "":
                print("⚖️  Evaluator-Critic 示例:")
                print("  /ec demo → 正例：硬约束文案（能挑错、也能改好）")
                print("  /ec bad  → 反例：缺信息（命中否决线④，批了也没用）")
                print("  /ec <任意任务> → 自定义任务")
                continue
            if rest == "demo":
                task = POSITIVE_TASK
            elif rest == "bad":
                task = NEGATIVE_TASK
            else:
                task = rest
            EvaluatorCritic(threshold=85, max_rounds=3).run(task)
            continue
        # 【Group Chat 模式】 /gc list | /gc demo | /gc <议题>
        if user_input.startswith("/gc"):
            rest = user_input[len("/gc"):].strip()
            if rest in ("list", ""):
                print("""
💬 Group Chat（去中心化协商）：
  · 参与者共享一个「频道」，都能看到全部发言 → 可互相质疑、修订
  · 与直接提问的区别：买的是「信息汇集 / 独立上下文」而非推理质量
  · 代价：token 随 参与者×轮数 放大

  /gc demo          → 内置案例（两位参与者各持私有信息）
  /gc <议题>         → 三角色小组（支持/反对/中立）辩论该议题

  适用：关键信息分散、需多方信息汇集或来源可审计的决策。
  不适用：单人不确定性推理（那用 solo 更省）。""")
                continue
            if rest == "demo":
                _gc_demo()
                continue
            _gc_panel(rest)
            continue
        # 【Contract Net 模式】 /cn list | /cn demo | /cn <任务>
        if user_input.startswith("/cn"):
            rest = user_input[len("/cn"):].strip()
            if rest in ("list", ""):
                print("""
📣 Contract Net（任务发标-投标-中标）：
  · 中央**不指定**，而是公告任务 → 候选人各自**报价** → 择优
  · 治的病：中央无法评估「这活该谁干」（能力/负载/工期是执行者的私有信息）
  · 与 Group Chat 的区别：那是协商「共识」，这是竞价「分配」（效率导向）
  · 代价：token ≈ 候选人数 × 单次（实测 ≈5×）

  /cn demo    → 内置案例（三位工程师各持私有信息）
  /cn <任务>   → 就该任务征集报价并择优（候选人按通用模板）

  适用：中央信息不足、需逼出执行者真实评估的分配问题。
  不适用：中央**能**评估时（直接指派更省）。""")
                continue
            if rest == "demo":
                _cn_demo()
                continue
            # 通用任务：默认三位候选人（需用户补充候选人/私有信息时，用 demo 模板）
            print("⚠️ 通用 /cn <任务> 需要候选人及其私有信息。")
            print("   请用 /cn demo 看内置案例，或在代码中按 ContractNet.add_bidder 方式接入。")
            continue
        # 【Debate 模式】 /debate list | /debate <议题>
        if user_input.startswith("/debate"):
            rest = user_input[len("/debate"):].strip()
            if rest in ("list", ""):
                print("""
⚔️  Debate（多 Agent 正反辩论）：
  · 结构化对抗：**立论 → 交叉反驳 → 中立裁决**（有固定轮次）
  · 与邻近结构的区别：Evaluator-Critic=自己批自己；Group Chat=自由协商；
    **Debate=强制对立立场 + 交叉攻击**
  · 代价：token ≈ 角色数 × 轮数（每次发言都带历史）

  /debate <议题>   → 正反双方就议题辩论并裁决

  ⚠️ 实测提醒：在强模型下，Debate 的必要性**未复现**——
     对有教科书答案的问题，单 Agent 自己就会质疑错误前提。
     它可能值得的场景：红队/安全审查、模型有已知偏见的领域、需攻防审计。
     详见 docs/02-编排章/debate-investigation.md。""")
                continue
            _debate_panel(rest)
            continue
        ma.run(user_input)


if __name__ == "__main__":
    main()
