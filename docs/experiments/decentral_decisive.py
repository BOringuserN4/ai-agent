# -*- coding: utf-8 -*-
"""去中心化协商专题 · 决定性实验（2026/10/06）

修正后的病根：**关键信息天然分散且不可推理时，集中式只能猜**。

本实验把私有事实设为「不可推理 + 相互冲突」，且**正确答案必须综合全部私有事实**：
  议题：把新服务流量切到 A 机房还是 B 机房？
  私有事实（各自持有，互相看不到）：
    · 网络：A 机房到主库的专线今天断了（临时故障，通用经验推不出）
    · 合规：B 机房没有等保资质，禁止承载生产流量（内部政策，不可推理）
  真值：**两个都不能选**——必须等专线修复或用备用方案。
       只知其一 → 会错误地选另一个；一无所知 → 只能猜。

对照：
  集中式臂：单 Agent，只有议题（无任何私有事实）
  去中心化臂：两个 Agent 各持一条私有事实，共享频道协商
指标：结论正误 + 是否引用了私有事实 + token 成本。
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TOPIC = "议题：把一个新服务的生产流量切到 A 机房还是 B 机房？请给出明确选择。"

FACTS = {
    "网络": "你的私有信息（刚收到的运维告警）：**A 机房的专线今天断了**，尚未恢复。",
    "合规": "你的私有信息（内部合规政策）：**B 机房没有等保资质**，禁止承载生产流量。",
}
TRUTH_KEYS = ["都不能", "两个都", "不切", "等待", "专线恢复", "都不行", "两个都不", "既不能", "等专线", "备用"]


def verdict(text):
    """粗判：是否识别出『两个都不能选』。"""
    return any(k in text for k in TRUTH_KEYS)


def arm_central():
    print("═" * 72)
    print("【集中式臂】单 Agent，只有议题")
    print("═" * 72)
    a = Agent(system_prompt="你是运维决策者，负责给出切流量方案。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(TOPIC, max_steps=4) or ""
    ok = verdict(out)
    print(out.strip()[:400])
    print(f"\n→ 识别「两个都不能选」: {'✅' if ok else '❌（选了错的方案）'}  token={a.usage['total_tokens']}")
    return ok, a.usage["total_tokens"]


def arm_decentral(rounds=2):
    print("\n" + "═" * 72)
    print("【去中心化臂】2 个 Agent 各持私有事实，共享频道协商")
    print("═" * 72)
    ags = {n: Agent(system_prompt=f"你是「{n}」负责人。{f}\n"
                                  f"你会看到共享频道历史；基于你的私有信息判断，该反对就反对。")
           for n, f in FACTS.items()}
    tr = []
    tok = 0
    for r in range(rounds):
        for n, ag in ags.items():
            hist = "\n".join(f"[{s}] {t}" for s, t in tr) or "（空）"
            with contextlib.redirect_stdout(io.StringIO()):
                o = ag.run(f"{TOPIC}\n\n【频道历史】\n{hist}\n\n轮到你（{n}）发言。", max_steps=3) or ""
            tr.append((n, o.strip())); tok += ag.usage["total_tokens"]
            print(f"\n— 第{r+1}轮 [{n}] —\n{o.strip()[:220]}")
    # 收敛（中立主持）
    mod = Agent(system_prompt="你是中立主持人，只根据频道记录收敛结论。")
    hist = "\n".join(f"[{s}] {t}" for s, t in tr)
    with contextlib.redirect_stdout(io.StringIO()):
        fin = mod.run(f"{TOPIC}\n\n【频道记录】\n{hist}\n\n给出统一结论。只基于记录。", max_steps=3) or ""
    tok += mod.usage["total_tokens"]
    ok = verdict(fin)
    print(f"\n【去中心化臂 · 统一结论】\n{fin.strip()[:400]}")
    print(f"\n→ 识别「两个都不能选」: {'✅' if ok else '❌'}  token={tok}")
    return ok, tok


if __name__ == "__main__":
    c_ok, c_tok = arm_central()
    d_ok, d_tok = arm_decentral()
    print("\n" + "=" * 72)
    print(f"集中式: {'✅' if c_ok else '❌'}  token={c_tok}")
    print(f"去中心化: {'✅' if d_ok else '❌'}  token={d_tok}")
    print("=" * 72)
