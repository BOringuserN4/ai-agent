# -*- coding: utf-8 -*-
"""agent/contract_net.py — Contract Net 编排（任务发布-投标-中标）

结构定位（2026/10/07）：
  - 谁做这个决定：**候选者自己报价，中央择优**（不是中央单方指定）。
  - 治什么病：**中央无法评估「这活该谁干」** —— 能力/负载/工期是执行者的**私有信息**，
    中央瞎派；让执行者**报价**，就把"猜"变成"陈述"。

实测依据（见 docs/02-编排章/contract-net-investigation.md）：
  中央无法评估时（简介无法区分候选人）：
    集中式直接指派 **33%（=三选一瞎猜）** vs Contract Net **100%**。
  代价：token ≈5×（随候选人数线性增长）。

与 group_chat.py 的分工：
  · Group Chat   = 协商达成**共识**（质量/正确性导向）；
  · Contract Net = 竞价择优**分配**（**分配效率**导向）——更接近"资源调度"。

何时**别用**：中央**能**评估时，直接指派更省（5× 开销白花）。
"""
import time

from agent.core import Agent


class ContractNet:
    """最小 Contract Net：公告 → 各自报价 → 择优。

    用法：
        cn = ContractNet()
        cn.add_bidder("甲", "你是工程师甲。你精通 Flink，当前空闲，1 天可修。")
        cn.add_bidder("乙", "你是工程师乙。你不熟 Flink，手头两个 deadline 今晚到期。")
        winner = cn.run("Flink 管道消费延迟积压 2 小时，需一位工程师接手。")
    """

    def __init__(self, award_prompt=None, verbose=True):
        """
        Args:
            award_prompt: 裁决者的 system prompt（负责按报价择优）。
            verbose: 打印过程。
        """
        self.verbose = verbose
        self.bidders = []          # [(name, Agent)]
        self.bids = {}             # name -> 报价文本
        self.awarder = Agent(
            system_prompt=award_prompt or (
                "你是任务负责人。你**只依据各人的报价**选出最能胜任、工期最短的一位。"
                "不要依据报价之外的信息，也不要凭空猜测。"
                "最后一行只写：中标=<名字>"
            ),
            tools=None,
        )
        self.awarder.tools_spec = []
        self.awarder.tool_registry = {}
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ---- 组装 ----
    def add_bidder(self, name, system_prompt, tools=None, memory=None):
        """加入一位候选者。system_prompt 里放该候选者的**私有信息**（中央看不到）。"""
        ag = Agent(system_prompt=system_prompt, tools=tools, memory=memory)
        self.bidders.append((name, ag))
        return ag

    def reset(self):
        self.bids = {}
        self.awarder.reset()

    @staticmethod
    def _accumulate(dst, usage):
        for k in dst:
            dst[k] += usage.get(k, 0)

    # ---- 主流程 ----
    def run(self, task, briefs=None):
        """跑一轮完整招标：公告 → 报价 → 择优。

        Args:
            task: 任务描述（公告）。
            briefs: 可选，{name: 公开简介}。公告里给候选人看的**公开**信息
                    （区别其私有信息 —— 公开简介无法区分谁最合适）。
        Returns:
            dict: {winner, bids, award_text, total_tokens}
        """
        print(f"\n{'═' * 62}\n📣 Contract Net · 任务：{task}\n"
              f"   候选者 {len(self.bidders)} 人\n{'═' * 62}")

        # 1) 公告
        desc = ""
        if briefs:
            desc = "\n\n【公开简介】（中央只知道这些，无法区分谁最合适）\n" + \
                   "\n".join(f"  {n}：{d}" for n, d in briefs.items())
        announce = (f"{task}{desc}\n\n请各位**报价**：能否承接、预计工期、当前是否有空。"
                    f"只依据你自己的实际情况，简短。")

        # 2) 各自报价（视角隔离：每人只看公告 + 自己的私有信息）
        for name, ag, in self.bidders:
            t0 = time.time()
            out = ag.run(announce, max_steps=2) or ""
            self._accumulate(self.usage, ag.usage)
            self.bids[name] = out.strip()
            if self.verbose:
                print(f"\n— 【{name}】报价（{round(time.time() - t0, 1)}s）—\n{out.strip()}")

        # 3) 择优（只看报价）
        bid_text = "\n\n".join(f"【{name}】报价：\n{b}" for name, b in self.bids.items())
        award = self.awarder.run(
            f"任务：{task}\n\n{bid_text}\n\n请据此选出中标者。只依据报价。",
            max_steps=2) or ""
        self._accumulate(self.usage, self.awarder.usage)

        winner = self._parse_winner(award)
        if self.verbose:
            print(f"\n{'═' * 62}\n🏆 【中标】{winner}\n{award.strip()}\n{'═' * 62}")
        return {"winner": winner, "bids": dict(self.bids),
                "award_text": award.strip(), "total_tokens": self.usage["total_tokens"]}

    @staticmethod
    def _parse_winner(text):
        """从裁决输出解析中标者：优先『中标=X』，否则取首个出现的已报价名字。"""
        import re
        if not text:
            return None
        m = re.search(r"中标\s*[=:：]\s*\**\s*([^\s，,。\n*]+)", text)
        if m:
            return m.group(1)
        return None

    def report(self):
        return {
            "bidders": [n for n, _, in self.bidders],
            "bids": len(self.bids),
            "total_tokens": self.usage["total_tokens"],
        }
