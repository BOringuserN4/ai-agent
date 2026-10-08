# -*- coding: utf-8 -*-
"""agent/debate.py — Debate 编排（多 Agent 正反辩论）

结构定位（2026/10/08）：
  - 谁控制流：**结构化对抗** —— 立论 → 交叉反驳 → 中立裁决（有固定轮次）。
  - 与邻近结构的区别：
    · `evaluator_critic.py` = **自己批自己**（同上下文，撞自我确认偏差）；
    · `group_chat.py`      = **自由发言协商**（无强制对立）；
    · **Debate**           = **强制对立立场 + 交叉攻击 + 裁决**。

实测边界（见 docs/02-编排章/debate-investigation.md）：
  ⚠️ 在强模型下，Debate 的**必要性未复现** —— 对「有教科书答案」的问题，
  单 Agent 自己就会质疑错误前提、自己就会权衡多约束（对照 6/6 vs 6/6、6/6 vs 5/6）。
  → 它**可能**有价值的场景：立场即对抗性输入（红队/安全）、模型有已知偏见的领域、
    需要攻防审计记录的决策。**上述边界未经实测。**

代价：token ≈ 角色数 × 轮数（每轮都带历史）。
"""
import time

from agent.core import Agent

DEFAULT_ROLES = [
    ("正方", "你是**正方**。尽力论证你支持的方案，反驳对方。"),
    ("反方", "你是**反方**。尽力找出对方方案的致命问题，并提出替代。"),
]


class Debate:
    """最小 Debate：立论 → 交叉反驳 → 裁决。

    用法：
        d = Debate(topic="该不该给这个服务加缓存层？")
        d.add_side("正方", "你支持加缓存…")
        d.add_side("反方", "你反对加缓存…")
        verdict = d.run()
    """

    def __init__(self, topic="", judge_prompt=None, rounds=1, verbose=True):
        """
        Args:
            topic: 辩论议题。
            judge_prompt: 裁决者 system prompt。
            rounds: **交叉反驳轮数**（代码封顶，不指望模型自己停）。
            verbose: 打印过程。
        """
        self.topic = topic
        self.verbose = verbose
        self.rounds = rounds
        self.sides = []            # [(name, Agent)]
        self.transcript = []       # [(name, text)]
        self.judge = Agent(
            system_prompt=judge_prompt or (
                "你是**中立裁决者**。综合双方攻防，给出**明确结论**（不要「取决于」），"
                "并说明采信了哪些论据、驳回了哪些、为什么。"
            ),
            tools=None,
        )
        self.judge.tools_spec = []
        self.judge.tool_registry = {}
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ---- 组装 ----
    def add_side(self, name, system_prompt):
        """加入一方（立场由 system_prompt 指定）。"""
        ag = Agent(system_prompt=system_prompt)
        self.sides.append((name, ag))
        return ag

    def reset(self):
        self.transcript = []
        self.judge.reset()

    @staticmethod
    def _acc(dst, usage):
        for k in dst:
            dst[k] += usage.get(k, 0)

    def _channel(self):
        return "\n\n".join(f"【{n}】{t}" for n, t in self.transcript) or "（暂无发言）"

    # ---- 主流程 ----
    def run(self, topic=None):
        """跑一轮完整辩论：立论 → 交叉反驳 × rounds → 裁决。"""
        topic = topic or self.topic
        print(f"\n{'═' * 62}\n⚔️  Debate · 议题：{topic}\n"
              f"   双方 {len(self.sides)} 人 · 交叉反驳 {self.rounds} 轮\n{'═' * 62}")

        # 1) 立论
        for name, ag in self.sides:
            t0 = time.time()
            out = ag.run(f"{topic}\n\n轮到你（{name}）**立论**：一段话说清你的立场与首要论据。",
                         max_steps=2) or ""
            self._acc(self.usage, ag.usage)
            self.transcript.append((name, out.strip()))
            if self.verbose:
                print(f"\n— 【{name}】立论（{round(time.time() - t0, 1)}s）—\n{out.strip()}")

        # 2) 交叉反驳
        for r in range(1, self.rounds + 1):
            for name, ag in self.sides:
                others = "、".join(n for n, _ in self.sides if n != name)
                prompt = (f"{topic}\n\n【当前辩论记录】\n{self._channel()}\n\n"
                          f"轮到你（{name}）**反驳**：针对 {others} 的具体论据逐条攻击，"
                          f"并承认自己立场的一处短板。简短有力。")
                t0 = time.time()
                out = ag.run(prompt, max_steps=2) or ""
                self._acc(self.usage, ag.usage)
                self.transcript.append((f"{name}·反驳{r}", out.strip()))
                if self.verbose:
                    print(f"\n— 【{name}·反驳{r}】（{round(time.time() - t0, 1)}s）—\n{out.strip()}")

        # 3) 裁决
        verdict = self.judge.run(
            f"议题：{topic}\n\n【完整辩论记录】\n{self._channel()}\n\n"
            f"请给出最终裁决：明确结论 + 采信/驳回的理由。",
            max_steps=3) or ""
        self._acc(self.usage, self.judge.usage)
        if self.verbose:
            print(f"\n{'═' * 62}\n⚖️  【裁决】\n{verdict.strip()}\n{'═' * 62}")
        return verdict.strip()

    def report(self):
        return {
            "sides": [n for n, _ in self.sides],
            "messages": len(self.transcript),
            "rounds": self.rounds,
            "total_tokens": self.usage["total_tokens"],
        }
