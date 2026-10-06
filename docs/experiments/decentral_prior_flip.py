# -*- coding: utf-8 -*-
"""去中心化协商专题 · 决定性实验 v2：先验反转（2026/10/06）

前几测集中式都"猜对"——因为通用先验够用。本测把私有事实设为**推翻先验**：
让"本能的正确答案"恰好是错的。

议题：一位老客户申请全额退款，该不该批？
先验（模型本能）：客服口径通常倾向"客户至上/按政策酌情批"。
私有事实（不可推理，且反转先验）：
  · 风控：该客户近 90 天内已申请 4 次退款，已被标记为**异常退款模式**。
  · 合同：该订单已超**无理由退款期**（第 37 天，超 30 天窗口）。
真值：**不该批全额退款**（或必须走特殊审批）。
只凭先验 → 会倾向"批"。

对照：集中式（只有议题）vs 去中心化（两 Agent 各持一条私有事实）。
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TOPIC = "议题：一位老客户申请全额退款 5000 元，该不该批准？请给出明确结论（批 / 不批）。"

FACTS = {
    "风控": "你的私有信息（风控系统）：该客户近 90 天内已 **申请 4 次退款**，已被标记为**异常退款模式**。",
    "合同": "你的私有信息（订单系统）：该订单已 **第 37 天**，超出 **30 天** 无理由退款窗口。",
}
DENY_KEYS = ["不批", "驳回", "拒绝", "不予", "需审批", "特殊审批", "不该批", "不能批", "走审批"]


def says_deny(t):
    return any(k in t for k in DENY_KEYS)


def arm_central():
    print("═" * 72)
    print("【集中式臂】单 Agent，只有议题（无私有事实）")
    print("═" * 72)
    a = Agent(system_prompt="你是客服主管，负责决定退款是否批准。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(TOPIC, max_steps=4) or ""
    print(out.strip()[:380])
    print(f"\n→ 结论为「不批/需审批」: {'✅' if says_deny(out) else '❌（凭先验批了）'}  token={a.usage['total_tokens']}")


def arm_decentral(rounds=2):
    print("\n" + "═" * 72)
    print("【去中心化臂】2 Agent 各持私有事实，协商")
    print("═" * 72)
    ags = {n: Agent(system_prompt=f"你是「{n}」负责人。{f}\n看到频道历史；基于私有信息判断，该反对就反对。")
           for n, f in FACTS.items()}
    tr, tok = [], 0
    for r in range(rounds):
        for n, ag in ags.items():
            hist = "\n".join(f"[{s}] {t}" for s, t in tr) or "（空）"
            with contextlib.redirect_stdout(io.StringIO()):
                o = ag.run(f"{TOPIC}\n\n【频道历史】\n{hist}\n\n轮到你（{n}）发言。", max_steps=3) or ""
            tr.append((n, o.strip())); tok += ag.usage["total_tokens"]
    mod = Agent(system_prompt="你是中立主持人，只根据频道记录收敛结论。")
    hist = "\n".join(f"[{s}] {t}" for s, t in tr)
    with contextlib.redirect_stdout(io.StringIO()):
        fin = mod.run(f"{TOPIC}\n\n【频道记录】\n{hist}\n\n给出统一结论。只基于记录。", max_steps=3) or ""
    tok += mod.usage["total_tokens"]
    print(fin.strip()[:400])
    print(f"\n→ 结论为「不批/需审批」: {'✅' if says_deny(fin) else '❌'}  token={tok}")


if __name__ == "__main__":
    arm_central()
    arm_decentral()
