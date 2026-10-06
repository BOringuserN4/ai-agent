# -*- coding: utf-8 -*-
"""agent/group_chat.py — Group Chat 编排（去中心化协商的最小实现）

结构定位（2026/10/06）：
  - 谁控制流：**没有中央调度者**。发言权在参与者之间轮转，内容决定走向。
  - 信息流：**共享频道**（transcript），每个参与者都能看到全部历史。
  - 与 multi_agent.py 的区别：那边是「中央分派 → 各自盲跑 → 汇总」，
    参与者**互相看不见**；这里参与者**共享上下文**，能互相质疑、修订。

为什么需要它（实测依据，见 docs/02-编排章/decentralized-investigation.md）：
  当关键信息**天然分散**在参与者手中、且**不可从先验推断**时，
  集中式只能靠通用先验「猜」——随机真值实验里准确率 33%（≈掷硬币），
  而能汇集分散信息的结构做到 100%。
  → Group Chat 买的不是「推理质量」（那被强模型吃掉了），
    而是 **信息汇集 / 来源可审计 / 独立上下文**。

代价（诚实标注）：
  · token ≈ 10×（每个参与者读全部历史）；
  · 可能绕圈 / 无人收敛 → **必须由代码封顶**（max_rounds）。
"""
import time

from agent.core import Agent


class GroupChat:
    """最小 Group Chat：共享频道 + 轮转发言 + 主持收敛。

    用法：
        gc = GroupChat()
        gc.add_participant("财务", "你是财务负责人。预算上限 50 万。")
        gc.add_participant("技术", "你是技术负责人。离线改造需 5 个月。")
        final = gc.run("这个项目该不该接？", rounds=2)
    """

    def __init__(self, moderator_prompt=None, max_rounds=3, verbose=True):
        """
        Args:
            moderator_prompt: 主持人 system prompt（负责收敛出统一结论）。
            max_rounds: **硬上限** —— 循环必须由代码封顶，不能指望模型自己停。
            verbose: 是否打印发言过程。
        """
        self.participants = []          # [(name, Agent)]
        self.transcript = []            # [(name, message)] —— 共享频道
        self.max_rounds = max_rounds
        self.verbose = verbose
        self.moderator = Agent(
            system_prompt=moderator_prompt or (
                "你是中立主持人。只根据频道记录收敛出最终结论："
                "综合各方发言，给出一个明确结论；标注关键依据来自谁。"
                "**只能使用记录里出现过的信息，不得新增或推测。**"
            ),
            tools=None,   # 主持人只汇总，不调工具
        )
        self.moderator.tools_spec = []
        self.moderator.tool_registry = {}
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ---- 组装 ----
    def add_participant(self, name, system_prompt, tools=None, memory=None):
        """加一名参与者。system_prompt 里可放该角色的**私有信息**。"""
        ag = Agent(system_prompt=system_prompt, tools=tools, memory=memory)
        self.participants.append((name, ag))
        return ag

    def reset(self):
        self.transcript = []
        for _, ag in self.participants:
            ag.reset()

    # ---- 内部：频道快照 ----
    def _channel(self):
        if not self.transcript:
            return "（频道暂无发言）"
        return "\n\n".join(f"【{name}】\n{msg}" for name, msg in self.transcript)

    @staticmethod
    def _accumulate(dst, usage):
        for k in dst:
            dst[k] += usage.get(k, 0)

    # ---- 主流程 ----
    def run(self, topic, rounds=None):
        """跑一轮完整协商：轮转发言 N 轮 → 主持收敛。

        Returns: 最终统一结论（str）。
        """
        rounds = rounds or self.max_rounds
        print(f"\n{'═' * 62}\n💬 Group Chat · 议题：{topic}\n"
              f"   参与者 {len(self.participants)} 人 · 轮转 {rounds} 轮\n{'═' * 62}")

        for r in range(1, rounds + 1):
            for name, ag in self.participants:
                prompt = (
                    f"【议题】{topic}\n\n"
                    f"【共享频道历史】\n{self._channel()}\n\n"
                    f"轮到你（{name}）发言：基于你掌握的（私有）信息给出判断；"
                    f"可以质疑前面的人，也可以在被说服时修订自己的结论。"
                    f"一段话说清，不要复述别人。"
                )
                t0 = time.time()
                out = ag.run(prompt, max_steps=3) or ""
                self._accumulate(self.usage, ag.usage)
                self.transcript.append((name, out.strip()))
                if self.verbose:
                    print(f"\n— 第{r}轮 【{name}】"
                          f"（{round(time.time() - t0, 1)}s）—\n{out.strip()}")

        # 主持收敛
        prompt = (
            f"【议题】{topic}\n\n"
            f"【完整频道记录】\n{self._channel()}\n\n"
            f"请据此给出**统一结论**：明确选择 + 关键依据来自谁。只基于记录。"
        )
        final = self.moderator.run(prompt, max_steps=3) or ""
        self._accumulate(self.usage, self.moderator.usage)
        if self.verbose:
            print(f"\n{'═' * 62}\n🧭 【主持人 · 统一结论】\n{final.strip()}\n{'═' * 62}")
        return final.strip()

    # ---- 观测 ----
    def report(self):
        """返回本轮成本与频道概况（便于对照集中式的 1× token）。"""
        return {
            "participants": [n for n, _ in self.participants],
            "messages": len(self.transcript),
            "total_tokens": self.usage["total_tokens"],
            "transcript": self.transcript,
        }
