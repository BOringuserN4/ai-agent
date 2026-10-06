# -*- coding: utf-8 -*-
"""Group Chat 实现验证（2026/10/06）

用「随机真值」决定性实验的同一批场景，验证 agent/group_chat.py：
  · Group Chat（信息持有者入频道 → 主持人收敛）应 ~100%
  · 对照：集中式臂（单 Agent + 受限 lookup）应 ~50%

复用 decentral_random_truth.py 的场景生成器，保证同源可比。
"""
import os, sys, io, random, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent
from agent.group_chat import GroupChat
from docs.experiments.decentral_random_truth import scenario, pick_of, arm_central, TRIALS


def via_group_chat(q, fact, opts):
    gc = GroupChat(max_rounds=1, verbose=False)
    gc.add_participant("信息持有者",
                       f"你是信息持有者。{fact}\n请把你掌握的、与决策相关的事实陈述出来。",
                       tools=())
    # 决策者作为第二参与者（也能看到频道）
    gc.add_participant("决策者",
                       "你是决策者。只根据频道里的事实做二选一决定。", tools=())
    final = gc.run(q + "\n最后一行只写：答案=<选项>", rounds=1)
    return final, pick_of(final, opts), gc.usage["total_tokens"]


if __name__ == "__main__":
    rng = random.Random(20261006)     # 与 decentral_random_truth 同种子
    c_hit = g_hit = 0
    c_tok = g_tok = 0
    print(f"{'场景':<10}{'真值':<8}{'集中式':<8}{'GroupChat':<11}gc_token")
    print("-" * 50)
    for t in range(TRIALS):
        name, q, fact, truth, opts = scenario(rng)
        _, cp = arm_central(q, opts)
        _, gp, gtok = via_group_chat(q, fact, opts)
        c_hit += cp == truth; g_hit += gp == truth
        # 集中式 token 实测均值 ≈2107（2026/10/06 实测：1738/2704/1879）
        c_tok += 2107; g_tok += gtok
        print(f"{name:<10}{truth:<8}{'✅' if cp == truth else '❌':<8}"
              f"{'✅' if gp == truth else '❌':<11}{gtok}")
    n = TRIALS
    print("\n" + "=" * 50)
    print(f"集中式   : {c_hit}/{n} = {c_hit/n:.0%}   ≈{c_tok//n} token/次")
    print(f"GroupChat: {g_hit}/{n} = {g_hit/n:.0%}   ≈{g_tok//n} token/次"
          f"  （{g_tok/max(c_tok,1):.1f}× 集中式）")
