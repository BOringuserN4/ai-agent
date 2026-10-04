# -*- coding: utf-8 -*-
"""复现「答案跨多条记忆」问题（记忆切分粒度专题, 2026/10/03）

issue-log 第 26 条：「我那只英短叫什么」——品种在 A、名字在 B，单文档检索答不了。

思路：模拟真实场景下「事实分两轮存入 → 两条独立记忆」，
再用多种自然问法查询，看两条是否都能被召回（score ≥ 阈值 0.46）。
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from agent.memory import MemoryStore, MIN_SCORE
from agent.extractor import build_embed_text

TMP = os.path.join(ROOT, "tmp-artifacts", "chroma_memchunk")
import shutil
shutil.rmtree(TMP, ignore_errors=True)

# 两条"分离"的记忆（模拟分两轮存入：先品种，后名字）
A = "用户养了一只英短猫"          # 品种
B = "用户的猫叫毛毛"              # 名字
QS_A = ["我养了什么猫", "我那只猫是什么品种", "我家的猫"]
QS_B = ["我的猫叫什么", "我那只猫的名字", "主子叫啥"]

# 用 build_embed_text 增富（模拟真实写入 path）
mem = MemoryStore(top_k=8, chroma_dir=TMP)
mem.add(A, meta={"tags": ["宠物"]}, embed_text=build_embed_text(A, QS_A))
mem.add(B, meta={"tags": ["宠物"]}, embed_text=build_embed_text(B, QS_B))
print(f"库中记忆：\n  A = {A}\n  B = {B}\n阈值 MIN_SCORE = {MIN_SCORE}\n")

queries = [
    "我那只英短叫什么",     # ★ 目标问法：同时需要 A（英短）和 B（名字）
    "我家猫叫什么名字",
    "我的猫是什么品种，叫什么",
    "我养的那只猫叫什么",
]
print(f"{'查询':<24}{'A(品种)分数':<14}{'B(名字)分数':<14}两条都过线?")
print("-" * 66)
for q in queries:
    hits = mem.search(q)
    d = {h["text"]: h["score"] for h in hits}
    sa, sb = d.get(A, 0.0), d.get(B, 0.0)
    both = "✅" if (sa >= MIN_SCORE and sb >= MIN_SCORE) else "❌"
    print(f"{q:<24}{sa:<14.4f}{sb:<14.4f}{both}")

# 对比：更粗的切分——两条事实合并成一条，会怎样？
print("\n--- 对照：把两条事实合并成 1 条记忆 ---")
mem2 = MemoryStore(top_k=8, chroma_dir=TMP + "_merged")
MERGED = "用户养了一只英短猫，这只猫叫毛毛"
mem2.add(MERGED, meta={"tags": ["宠物"]},
         embed_text=build_embed_text(MERGED, QS_A + QS_B))
print(f"{'查询':<24}{'合并条分数':<14}过线?")
print("-" * 46)
for q in queries:
    hits = mem2.search(q)
    s = hits[0]["score"] if hits else 0.0
    print(f"{q:<24}{s:<14.4f}{'✅' if s >= MIN_SCORE else '❌'}")


# ---- 场景 2：无增富（裸文本 embedding，模拟老记忆/未增富）----
print("\n========== 场景 2：无增富（裸文本） ==========")
mem3 = MemoryStore(top_k=8, chroma_dir=TMP + "_raw")
mem3.add(A, meta={"tags": ["宠物"]})     # 不传 embed_text
mem3.add(B, meta={"tags": ["宠物"]})
print(f"{'查询':<24}{'A(品种)':<12}{'B(名字)':<12}两条都过线?")
print("-" * 62)
for q in queries:
    hits = mem3.search(q)
    d = {h["text"]: h["score"] for h in hits}
    sa, sb = d.get(A, 0.0), d.get(B, 0.0)
    both = "✅" if (sa >= MIN_SCORE and sb >= MIN_SCORE) else "❌"
    print(f"{q:<24}{sa:<12.4f}{sb:<12.4f}{both}")


# ---- 场景 3：两条记忆间无共同实体词（更苛刻）----
print("\n========== 场景 3：无共同实体词（品种用“英国短毛”、名字用“宠物”） ==========")
A2 = "用户养了一只英国短毛猫"
B2 = "用户的宠物叫毛毛"                  # 不提“猫”也不提“英短”
mem4 = MemoryStore(top_k=8, chroma_dir=TMP + "_noent")
mem4.add(A2, meta={"tags": ["宠物"]}, embed_text=build_embed_text(A2, ["我养了什么猫", "我那只猫是何品种"]))
mem4.add(B2, meta={"tags": ["宠物"]}, embed_text=build_embed_text(B2, ["我的宠物叫什么名字", "它叫什么"]))
print(f"{'查询':<24}{'A2(品种)':<12}{'B2(名字)':<12}两条都过线?")
print("-" * 62)
for q in ["我那只英短叫什么", "我家猫叫什么名字", "我养的猫叫啥"]:
    hits = mem4.search(q)
    d = {h["text"]: h["score"] for h in hits}
    sa, sb = d.get(A2, 0.0), d.get(B2, 0.0)
    both = "✅" if (sa >= MIN_SCORE and sb >= MIN_SCORE) else "❌"
    print(f"{q:<24}{sa:<12.4f}{sb:<12.4f}{both}")


# ---- 场景 4：拥挤（大量干扰记忆）→ 细粒度切分的真软肋 ----
print("\n========== 场景 4：加入 14 条干扰记忆后 ==========")
mem5 = MemoryStore(top_k=8, chroma_dir=TMP + "_crowd")
mem5.add(A, meta={"tags": ["宠物"]}, embed_text=build_embed_text(A, QS_A))
mem5.add(B, meta={"tags": ["宠物"]}, embed_text=build_embed_text(B, QS_B))
distractors = [
    "用户是一名测试开发工程师", "用户喜欢用 Python", "用户住在上海",
    "用户的同事叫李工", "用户喜欢喝美式咖啡", "用户上周去了朝阳公园",
    "用户的手机是 iPhone", "用户在学 AI Agent", "用户的孩子叫小满",
    "用户对花生过敏", "用户每天 7 点起床", "用户喜欢看科幻小说",
    "用户的车是特斯拉", "用户最喜欢的城市是杭州",
]
for i, dt in enumerate(distractors):
    mem5.add(dt, meta={"tags": ["其他"]}, embed_text=dt)
print(f"库中共 {mem5.count()} 条记忆，top_k=8\n")
print(f"{'查询':<24}{'A排名':<8}{'B排名':<8}{'两条都在 top8?':<16}{'两条都过线?'}")
print("-" * 70)
for q in queries:
    hits = mem5.search(q)
    texts = [h["text"] for h in hits]
    ra = texts.index(A) + 1 if A in texts else -1
    rb = texts.index(B) + 1 if B in texts else -1
    in_top = "✅" if (A in texts and B in texts) else "❌"
    d = {h["text"]: h["score"] for h in hits}
    both = "✅" if (d.get(A, 0) >= MIN_SCORE and d.get(B, 0) >= MIN_SCORE) else "❌"
    print(f"{q:<24}{str(ra):<8}{str(rb):<8}{in_top:<16}{both}")


# ---- 场景 5：需「推理桥」的多跳（查询只命中其中一条的字面）----
print("\n========== 场景 5：需推理桥的多跳 ==========")
A5 = "用户对猫毛过敏"
B5 = "英短掉毛比较严重"
mem6 = MemoryStore(top_k=8, chroma_dir=TMP + "_bridge")
mem6.add(A5, meta={"tags": ["健康"]}, embed_text=build_embed_text(A5, ["我对什么过敏", "我能不能养猫"]))
mem6.add(B5, meta={"tags": ["宠物"]}, embed_text=build_embed_text(B5, ["英短掉毛吗", "英短有什么缺点"]))
print(f"  A5 = {A5}  （回答“能否养英短”必需）")
print(f"  B5 = {B5}  （查询直接命中）\n")
print(f"{'查询':<22}{'A5(过敏)':<12}{'B5(掉毛)':<12}两条都过线?")
print("-" * 60)
for q in ["我能养英短吗", "我可以养只英短吗", "养英短合适吗", "我适合养猫吗"]:
    hits = mem6.search(q)
    d = {h["text"]: h["score"] for h in hits}
    sa, sb = d.get(A5, 0.0), d.get(B5, 0.0)
    both = "✅" if (sa >= MIN_SCORE and sb >= MIN_SCORE) else "❌"
    print(f"{q:<22}{sa:<12.4f}{sb:<12.4f}{both}")
