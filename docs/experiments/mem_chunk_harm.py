# -*- coding: utf-8 -*-
"""危害验证：写侧丢上下文 → 是否真导致答错？（2026/10/03）

假设：逐轮抽取丢指代（"它"→"宠物或某个对象"），
      在「只有一只宠物」时无害（模型能推断），
      但在「多只宠物」时**信息不足以区分** → 应暴露答错。

对照：
  A. 含糊记忆（逐轮抽取的真实产物）：两条"有一只宠物名叫X"
  B. 上下文感知记忆：   "英短猫叫毛毛" / "金毛犬叫大黄"
问：我的猫叫什么名字？我的狗叫什么名字？
"""
import os, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)

from agent.memory import MemoryStore
from agent.core import Agent

QUERIES = [
    ("我的猫叫什么名字？", "毛毛"),
    ("我的狗叫什么名字？", "大黄"),
]

VAGUE = [   # 逐轮抽取的真实产物（代词丢了指代）
    "用户有一只宠物名叫「毛毛」",
    "用户有一只宠物名叫「大黄」",
]
CONTEXT = [  # 上下文感知应有的形态
    "用户的英短猫名叫「毛毛」",
    "用户的金毛犬名叫「大黄」",
]


def build(mem_texts, tag):
    d = os.path.join(ROOT, "tmp-artifacts", f"chroma_harm_{tag}")
    shutil.rmtree(d, ignore_errors=True)
    m = MemoryStore(top_k=8, chroma_dir=d)
    for t in mem_texts:
        m.add(t, meta={"tags": ["pet"]})
    return m


def ask(mem, q):
    a = Agent(system_prompt="你是一个乐于助人的助手。", memory=mem)
    return a.run(q, max_steps=3)


def score(name, mem_texts):
    m = build(mem_texts, name)
    print(f"\n========== 组 {name} ==========")
    print("记忆库：")
    for t in mem_texts:
        print("   -", t)
    ok = 0
    for q, expect in QUERIES:
        ans = (ask(m, q) or "")
        # 判定：出现正确名字，且**没有声明"无法区分"**
        cant = any(k in ans for k in ["没有记录", "无法区分", "不清楚哪", "没法确定", "哪一只", "无法确定"])
        good = (expect in ans) and not cant
        ok += good
        print(f"\n  问：{q}  期望：{expect}")
        print(f"  答：{ans.strip()[:80]!r}")
        print(f"  → {'✅ 正确' if good else '❌ 无法区分/答错'}" + ("  [声明无法区分]" if cant else ""))
    return ok


if __name__ == "__main__":
    a = score("A_vague", VAGUE)
    b = score("B_context", CONTEXT)
    print(f"\n{'='*50}")
    print(f"含糊记忆正确数：{a}/2    上下文感知：{b}/2")
