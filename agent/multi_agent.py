# -*- coding: utf-8 -*-
"""
agent/multi_agent.py — 多 Agent 调度器（Router + Worker 架构）

这是你的第一个 Multi-Agent 示例！思路：
  - 一个「调度者 Router」：识别用户意图，决定交给哪个「专家 Worker」。
  - 几个「专家 Worker」：数学、天气、通用，各司其职、各有工具。

流程：
  用户输入 → Router 判断该交给谁 → 委派给对应 Worker → Worker 用自己的工具
  与人格独立处理 → 把结果返回给 Router → Router 汇总回给用户。

用到了之前学到的：
  - Agent 可配置不同 system_prompt（人格）和不同工具集。
  - Tracer 记录每步，可观测。
  - Router 本身也是一个 Agent，但它「只决策、不干活」，输出 JSON 指定交给谁。
"""
import json
from agent.core import Agent
from agent.roles import ROLE_FACTORIES
from agent.memory import MemoryStore


class MultiAgent:
    def __init__(self, use_memory=True):
        # 长期记忆库：所有专家共享，跨会话记住用户信息
        self.memory = MemoryStore() if use_memory else None
        if self.memory:
            print(f"🧠 长期记忆已启用，当前已有 {self.memory.count()} 条记忆")

        # Router：一个轻量 Agent，只负责拆任务、指派专家，不执行任务
        self.router = Agent(
            system_prompt=(
                "你是任务调度器。请把用户问题拆成若干「子任务」，每个子任务指派一位专家。\n"
                '只输出一个 JSON：{"tasks": [{"expert": "math|weather|general", '
                '"subtask": "该专家只需要处理的那一部分"}]}\n'
                "规则：\n"
                "- 数学/计算类→math；天气气温类→weather；其他→general。\n"
                "- 单一问题只拆一个子任务；跨领域问题拆成多个子任务。\n"
                "- subtask 必须自包含、具体（例：'计算 (88+12)*3'、'查询广州当前天气'），\n"
                "  不要把整道题原样丢给每个专家。\n"
                "只输出 JSON，不要其他文字。"
            ),
            tools=None,  # 调度器不需要工具
        )
        # 归并员（Fan-in）：把各专家的子结果合成一段连贯回答
        self.merger = Agent(
            system_prompt=(
                "你是结果汇总员。把下面各位专家对各自子任务的结果，"
                "整合成一段连贯、不重复、无矛盾的中文回答。"
                "只能使用给定信息，不要新增内容、不要自行计算或推测。"
            ),
            tools=None,
        )
        # 专家 Worker 们（懒加载，复用同一份配置）
        self.experts = {}
        for name, factory in ROLE_FACTORIES.items():
            # 给专家接入共享的记忆库
            if self.memory:
                agent_obj = factory()
                agent_obj.memory = self.memory
                self.experts[name] = agent_obj
            else:
                self.experts[name] = factory()

    def _plan(self, user_input: str) -> list:
        """让 Router 把问题拆成「子任务」并指派专家，返回 [{expert, subtask}]。

        这是真·Fan-out 的关键：不是把整题群发给多个专家，而是先切分任务，
        每个子任务只含该专家职责内的那部分。这样能避免：
          - 重复回答（两个专家都答全题）
          - 越权心算（天气专家去算数学）
          - 自相矛盾（各说「这半不归我管」）
        兼容旧格式（experts / expert 字段）。
        """
        self.router.reset()  # 每次重新规划，避免历史干扰
        result = self.router.run_traced(user_input, trace_name="router", user_id="demo")
        print(f"🧭 Router 规划 → {result}")
        tasks = []
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            data = json.loads(result[start:end])
            raw = data.get("tasks")
            if raw is None and data.get("experts"):
                raw = [{"expert": e, "subtask": user_input} for e in data["experts"]]
            if raw is None and data.get("expert"):
                raw = [{"expert": data["expert"], "subtask": user_input}]
            for t in (raw or []):
                exp = t.get("expert")
                sub = t.get("subtask") or user_input
                if exp in self.experts and not any(x["expert"] == exp for x in tasks):
                    tasks.append({"expert": exp, "subtask": sub})
        except Exception:
            pass
        if not tasks:
            tasks = [{"expert": "general", "subtask": user_input}]
        return tasks

    def run(self, user_input: str):
        """完整流程：规划 → 分发子任务（Fan-out）→ 归并（Fan-in）。

        单子任务：直接委派（保持最简路径）。
        多子任务：每位专家只收到自己的子任务，最后用归并员合成统一回答。
        """
        tasks = self._plan(user_input)
        experts = [t["expert"] for t in tasks]
        print(f"→ 交给专家：{', '.join(experts)}")

        if len(tasks) == 1:
            expert = tasks[0]["expert"]
            worker = self.experts[expert]
            worker.reset()
            answer = worker.run_traced(user_input, trace_name=f"expert-{expert}", user_id="demo")
            print(f"\n👥 [Multi-Agent] 汇总：「{expert}」专家完成：")
            print(f"   {answer}")
            return answer

        # 多子任务：Fan-out（各专家只答自己那部分）→ Fan-in（归并）
        parts = []
        for t in tasks:
            expert, subtask = t["expert"], t["subtask"]
            worker = self.experts[expert]
            worker.reset()
            ans = worker.run_traced(subtask, trace_name=f"expert-{expert}", user_id="demo")
            parts.append((expert, subtask, ans))
        answer = self._merge(user_input, parts)
        print(f"\n👥 [Multi-Agent] 汇总：{len(tasks)} 位专家完成并归并：")
        print(f"   {answer}")
        return answer

    def _merge(self, user_input: str, parts: list) -> str:
        """Fan-in：把各专家子结果合成一段连贯回答。"""
        blocks = "\n".join(
            f"[{e}] 子任务：{s}\n结果：{a}" for e, s, a in parts
        )
        prompt = (
            f"【用户原问题】{user_input}\n\n【各专家结果】\n{blocks}\n\n"
            "请整合成最终回答（不要重复、不要自相矛盾、不要新增信息）。"
        )
        self.merger.reset()
        return self.merger.run_traced(prompt, trace_name="merge", user_id="demo")

    def print_traces(self):
        """打印所有参与 Agent 的本轮轨迹。"""
        print("════════ Router 轨迹 ════════")
        self.router.print_trace()
        print("════════ Worker 轨迹 ════════")
        for name, w in self.experts.items():
            if w.tracer.steps:
                print(f"--- {name} ---")
                w.print_trace()

    def run_detailed(self, user_input: str) -> dict:
        """完整流程，但返回结构化数据（供 Web 前端展示过程）。

        Returns:
            dict: {
                'expert': 主专家名（首个，兼容旧字段）,
                'experts': 选中的全部专家名列表,
                'answer': 最终答案,
                'router_trace': Router 轨迹步骤列表,
                'expert_trace': 专家轨迹步骤列表,
                'usage': {token统计},
            }
        """
        tasks = self._plan(user_input)
        experts = [t["expert"] for t in tasks]
        all_steps = []
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        parts = []
        for t in tasks:
            expert, subtask = t["expert"], t["subtask"]
            worker = self.experts[expert]
            worker.reset()
            ans = worker.run(subtask if len(tasks) > 1 else user_input)
            parts.append((expert, subtask, ans))
            all_steps.extend(worker.tracer.steps)
            for k in usage_total:
                usage_total[k] += worker.usage.get(k, 0)
        answer = (self._merge(user_input, parts) if len(tasks) > 1
                  else parts[0][2])

        def steps_to_list(agent_steps):
            return [
                {
                    "type": s.type,
                    "detail": s.detail,
                    "tool": s.tool,
                    "args": s.args,
                    "result": s.result,
                    "duration_ms": s.duration_ms,
                }
                for s in agent_steps
            ]

        return {
            "expert": experts[0],       # 兼容旧字段（主专家）
            "experts": experts,
            "answer": answer,
            "router_trace": steps_to_list(self.router.tracer.steps),
            "expert_trace": steps_to_list(all_steps),
            "usage": usage_total,
        }


def main():
    ma = MultiAgent()
    print("=" * 50)
    print("🤖 Multi-Agent 已启动（Router + 专家）")
    print("  试试：帮我算 123*456  /  上海天气  /  随便聊聊")
    print("  指令：/traces 看所有轨迹 | /exit 退出")
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
        if user_input.lower() == "/traces":
            ma.print_traces()
            continue
        ma.run(user_input)


if __name__ == "__main__":
    main()
