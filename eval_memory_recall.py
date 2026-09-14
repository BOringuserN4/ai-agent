# -*- coding: utf-8 -*-
"""
eval_memory_recall.py — 记忆召回质量迷你评测（2026/09/13）

目的：不靠"感觉"，用数字回答三个问题：
  1. 相关的 query，能不能把对应的那条记忆"拉开"（分数明显更高）？
  2. 不相关的 query，分数是不是也落在同一区间（= 地板，分不开）？
  3. 阈值(threshold)定在多少，能让"该召回的留下、不该召回的丢掉"？

用法：
  ./.venv/bin/python eval_memory_recall.py

⚠️ 它用独立的 chroma_data_eval/ 目录，不碰你的真实记忆库。
"""
import os
import sys

# ---- 让脚本能 import agent 包 ----
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent.memory as mem

# ============================================================
# 1) 测试语料：8~10 条（你填，最少 8 条）
#    格式：("记忆内容", "类型")
# ============================================================
MEMORIES = [
    ("Python 是一种解释型编程语言", "manual"),
    ("机器学习需要大量数据进行训练", "manual"),
    ("向量数据库可以实现语义搜索", "manual"),
    ("ChromaDB 是一个本地向量数据库", "manual"),
    ("用户喜欢在早上喝咖啡", "manual"),
    ("用户养了一只叫豆豆的猫", "manual"),
    ("Langfuse 用于上报 Agent 的追踪数据", "manual"),
    ("上海今天多云，气温 24 度", "manual"),
    ("我当前是一个测试开发工程师，对agent开发感兴趣", "manual"),
    ("agent工程师需要了解记忆系统、上下文工程和评测工程等", "manual")
]

# ============================================================
# 2) 测试用例：每条 query 你"心里有数"的正确答案
#    expect = 该召回的记忆下标（从 0 数）；None = 一条都不该召回
# ============================================================
CASES = [
    {"query": "什么是向量数据库？",          "expect": 2},
    {"query": "Chroma 是干什么的？",         "expect": 3},
    {"query": "我的猫叫什么名字？",           "expect": 5},
    {"query": "今天晚饭吃什么好呢？",         "expect": None},   # 库里没有相关内容
    {"query": "帮我写一段快速排序代码",       "expect": None},
    {"query": "agent工程师需要了解什么",       "expect": 9},# 库里没有相关内容
    {"query": "Langfuse是干什么用的",       "expect": 6},
    {"query": "什么是python",              "expect": 0},
    {"query": "介绍一下华为公司的计算业务",    "expect": None},
    {"query": "介绍一下英伟达当前的计算业务",   "expect": None},
]

# ============================================================
# 3) 要扫描的阈值候选
# ============================================================
THRESHOLDS = [0.0, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]


def build_store():
    """建一个独立的评测用记忆库（别污染真实库）。"""
    mem.CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data_eval")
    mem.COLLECTION_NAME = "memory_eval"
    store = mem.MemoryStore(top_k=4)
    store.clear()                      # 每次跑都从干净状态开始
    for text, kind in MEMORIES:
        store.add(text, {"type": kind})
    return store


def main():
    if len(MEMORIES) < 8:
        print(f"⚠️  语料只有 {len(MEMORIES)} 条，至少 8 条才有意义")
    if len(CASES) < 6:
        print(f"⚠️  用例只有 {len(CASES)} 条，至少 6 条（含 2 条反例）")

    store = build_store()
    print(f"\n📚 记忆库：{store.count()} 条 | 用例：{len(CASES)} 条\n")

    # ---- 逐条 query：打印全部候选分数 ----
    all_rows = []      # (expect, [(idx, score), ...])
    for case in CASES:
        q, expect = case["query"], case["expect"]
        res = store.search(q, top_k=len(MEMORIES))   # 全量返回，才能看清分布
        # 把 text 映射回下标
        scored = []
        for r in res:
            idx = next((i for i, (t, _) in enumerate(MEMORIES) if t == r["text"]), -1)
            scored.append((idx, r["score"]))

        print(f"🔍 {q}   （期望：{'不召回' if expect is None else MEMORIES[expect][0]}）")
        for idx, score in scored:
            mark = ""
            if expect is not None and idx == expect:
                mark = "  ← 🎯 期望命中"
            elif expect is None:
                mark = "  ← ⚠️ 不该召回却出现了"
            print(f"     {score:.4f}  {MEMORIES[idx][0][:24]}{mark}")
        print()
        all_rows.append((expect, scored))

    # ---- 阈值扫描：每个阈值下"判对"几个 query ----
    print("=" * 62)
    print("阈值扫描（判对 = 期望召回的留下了 且 不该召回的被丢掉）")
    print("=" * 62)
    print(f"{'阈值':>6} | {'判对':>4} | {'漏召':>4} | {'误召':>4} | 通过率")
    print("-" * 62)
    for th in THRESHOLDS:
        ok = miss = false_pos = 0
        for expect, scored in all_rows:
            kept = [idx for idx, s in scored if s >= th]
            if expect is None:
                if kept:
                    false_pos += 1        # 不该召回却留下了
                else:
                    ok += 1
            else:
                if expect in kept:
                    ok += 1
                else:
                    miss += 1             # 该召回的被阈值挡掉了
        rate = ok / len(all_rows)
        print(f"{th:>6.2f} | {ok:>4} | {miss:>4} | {false_pos:>4} | {rate:>5.0%}")
    print("\n怎么读这张表：")
    print("  · 阈值=0.00 是现状（全收）→ 误召最多")
    print("  · 阈值越高 → 误召变少，但漏召变多")
    print("  · 找『误召=0 且 漏召=0』的那一行 → 那就是你要的阈值")
    print("  · 如果没有这一行 → 说明分数分不开，单靠阈值救不了（要换嵌入/切块/加 rerank）")


if __name__ == "__main__":
    main()
