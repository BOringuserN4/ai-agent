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


class MultiAgent:
    def __init__(self):
        # Router：一个轻量 Agent，只负责判断去哪，不执行任务
        self.router = Agent(
            system_prompt=(
                "你是任务调度器。根据用户问题，判断应该交给哪一位专家处理，"
                "并只输出一个 JSON：{\"expert\": \"math|weather|general\"}。"
                "数学/计算类→math；天气气温类→weather；其他→general。"
                "只输出 JSON，不要其他文字。"
            ),
            tools=None,  # 调度器不需要工具
        )
        # 专家 Worker 们（懒加载，复用同一份配置）
        self.experts = {}
        for name, factory in ROLE_FACTORIES.items():
            self.experts[name] = factory()

    def _route(self, user_input: str) -> str:
        """让 Router 判断该交给谁，解析出 expert 名字。"""
        self.router.reset()  # 每次重新判断，避免历史干扰
        result = self.router.run(user_input)
        print(f"🧭 Router 判断 → {result}")
        try:
            # 从输出里提取 JSON
            start = result.find("{")
            end = result.rfind("}") + 1
            data = json.loads(result[start:end])
            expert = data.get("expert", "general")
        except Exception:
            expert = "general"
        if expert not in self.experts:
            expert = "general"
        return expert

    def run(self, user_input: str):
        """完整流程：路由 + 委派 + 汇总。"""
        expert = self._route(user_input)
        print(f"→ 交给专家：{expert}")
        worker = self.experts[expert]
        worker.reset()
        answer = worker.run(user_input)
        # 汇总
        print(f"\n👥 [Multi-Agent] 汇总：「{expert}」专家完成：")
        print(f"   {answer}")
        return answer

    def print_traces(self):
        """打印所有参与 Agent 的本轮轨迹。"""
        print("════════ Router 轨迹 ════════")
        self.router.print_trace()
        print("════════ Worker 轨迹 ════════")
        for name, w in self.experts.items():
            if w.tracer.steps:
                print(f"--- {name} ---")
                w.print_trace()


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
