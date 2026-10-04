# -*- coding: utf-8 -*-
"""验证修复：给抽取器补 3 轮上下文后（2026/10/04）

三件要验的：
  1. 指代消解： 「我养了一只英短猫」→「它叫毛毛」→ 应抽成「英短猫叫毛毛」
  2. 无重复窃取：背景不得被重复抽取（记忆条数不膨胀）
  3. 危害消除： 多宠物场景，猫/狗名字都能对应到物种 → 查询 2/2
"""
import os, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.extractor import MemoryExtractor, build_embed_text
from agent.memory import MemoryStore
from agent.core import Agent

ex = MemoryExtractor()
TMP = os.path.join(ROOT, "tmp-artifacts", "chroma_fix_validate")


def fresh(name):
    d = os.path.join(TMP, name)
    shutil.rmtree(d, ignore_errors=True)
    return MemoryStore(top_k=8, chroma_dir=d)


def remember(mem, r):
    if r.get("keep") and r.get("text"):
        tags = r.get("tags", [])
        stored = f"[{','.join(tags)}] {r['text']}" if tags else r["text"]
        embed = build_embed_text(r["text"], r.get("questions"))
        mem.add(stored, meta={"tags": tags},
                embed_text=f"[{','.join(tags)}] {embed}" if tags else embed)


# ---------- 1+2. 指代消解 & 无重复窃取 ----------
print("=" * 60)
print("【测试 1+2】指代消解 + 无重复窃取")
print("=" * 60)
mem = fresh("t12")
t1 = ("我养了一只英短猫", "英短是很可爱的品种，性格温顺。")
t2 = ("它叫毛毛", "好的，毛毛这个名字很好听！")
r1 = ex.extract(*t1)
remember(mem, r1)
r2 = ex.extract(t2[0], t2[1], context=[t1])   # ← 关键：带上下文
remember(mem, r2)
print(f"轮1 抽取: {r1.get('text')!r}")
print(f"轮2 抽取(带上下文): {r2.get('text')!r}")
memories = mem.all_texts()
print(f"\n库中记忆 {len(memories)} 条（应为 2 条、无重复）：")
for m in memories:
    print("   -", m)
dup = len(memories) > 2
print(f"重复窃取：{'❌ 有' if dup else '✅ 无'}")

# ---------- 3. 危害消除：多宠物 ----------
print("\n" + "=" * 60)
print("【测试 3】多宠物危害场景")
print("=" * 60)
mem2 = fresh("t3")
turns = [
    ("我养了一只英短猫", "英短很可爱"),
    ("它叫毛毛", "好的"),
    ("我还养了一只金毛犬", "金毛很忠诚"),
    ("它叫大黄", "好的"),
]
ctx = []
for u, a in turns:
    r = ex.extract(u, a, context=ctx if ctx else None)
    remember(mem2, r)
    print(f"  {u!r} → {r.get('text')!r}")
    ctx.append((u, a))
print(f"\n库中 {mem2.count()} 条记忆：")
for m in mem2.all_texts():
    print("   -", m)

print("\n查询验证：")
for q, expect in [("我的猫叫什么名字？", "毛毛"), ("我的狗叫什么名字？", "大黄")]:
    ag = Agent(system_prompt="你是乐于助人的助手。", memory=mem2)
    ans = (ag.run(q, max_steps=3) or "")
    cant = any(k in ans for k in ["没有记录", "无法区分", "哪一只", "无法确定", "不清楚哪"])
    good = expect in ans and not cant
    print(f"  问：{q}")
    print(f"  答：{ans.strip()[:70]!r}")
    print(f"  → {'✅ 正确' if good else '❌ 未解决'}")
