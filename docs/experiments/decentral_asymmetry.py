# -*- coding: utf-8 -*-
"""去中心化协商专题 · 决定性实验：信息不对称下，集中式是否不可替代（2026/10/06）

假说的修正：互评的"视角"不是关键（自评也能切视角）。
真正的关键 = **关键信息天然分散在参与者手中，且无法事先集中**。

设计：
  私有事实（各自 system prompt 独有，互相看不到）：
    · 财务 Agent 知道：预算上限 50 万
    · 交付 Agent 知道：客户要求 3 个月内交付、必须支持离线
    · 技术 Agent 知道：现有架构不支持离线，改造需 5 个月
  议题：「这个项目该不该接？」

  集中式臂：单个 Agent，**只拿到议题**（中央拿不到任何私有事实）→ 会怎样？
  去中心化臂：三个 Agent 共享频道轮流发言（各自只带私有事实）→ 能否收敛出结论？
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TOPIC = "议题：客户想要一个「支持离线使用、3 个月内交付」的项目，我们的团队该不该接？"

PRIVATE = {
    "财务": "你的私有信息：项目预算上限是 **50 万元**（客户报价也是 50 万，等于零利润）。",
    "交付": "你的私有信息：客户硬性要求 **3 个月内交付**，且**必须支持离线**。",
    "技术": "你的私有信息：现有架构**不支持离线**，改造成离线能力需要 **5 个月**。",
}


def arm_central():
    print("\n" + "═" * 70)
    print("【集中式臂】单个 Agent，只拿到议题（中央没有私有事实）")
    print("═" * 70)
    a = Agent(system_prompt="你是团队负责人，负责判断项目该不该接。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(TOPIC + "\n请给出结论：接 / 不接，并说明理由。", max_steps=4)
    print((out or "").strip()[:600])


def arm_decentral(rounds=3):
    print("\n" + "═" * 70)
    print(f"【去中心化臂】3 个 Agent 共享频道，各带私有事实，轮流发言 {rounds} 轮")
    print("═" * 70)
    agents = {}
    for name, priv in PRIVATE.items():
        agents[name] = Agent(system_prompt=f"你是「{name}」专家。{priv}\n"
                                            f"你会看到共享频道的发言历史；基于你的私有信息给出判断。"
                                            f"该反对就反对，不要替别人假设信息。")
    transcript = []

    def snapshot():
        return "\n".join(f"[{s}] {t}" for s, t in transcript) or "（还没人发言）"

    for r in range(1, rounds + 1):
        for name, ag in agents.items():
            prompt = (f"{TOPIC}\n\n【共享频道历史】\n{snapshot()}\n\n"
                      f"轮到你（{name}）发言：给出你的判断，可质疑前面的人，"
                      f"但**只能基于你的私有信息**。一段话说清。")
            with contextlib.redirect_stdout(io.StringIO()):
                out = ag.run(prompt, max_steps=3)
            transcript.append((name, (out or "").strip()))
            print(f"\n— 第{r}轮 [{name}] —\n{(out or '').strip()[:300]}")

    # 收敛
    mod = Agent(system_prompt="你是中立主持人，只根据频道记录收敛出最终结论。")
    prompt = (f"{TOPIC}\n\n【完整频道记录】\n{snapshot()}\n\n"
              f"请根据这些发言，给出**统一结论**（接 / 不接）及关键依据。只基于记录，不要新增信息。")
    with contextlib.redirect_stdout(io.StringIO()):
        final = mod.run(prompt, max_steps=3)
    print(f"\n【去中心化臂 · 最终结论】\n{(final or '').strip()[:600]}")


if __name__ == "__main__":
    arm_central()
    arm_decentral()
