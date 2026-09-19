# -*- coding: utf-8 -*-
"""
eval_embedding_compare.py — 云端 / 本地 embedding 的 A/B 对比（2026/09/19）

背景：本地主机（Windows + RX 7900 GRE）跑 Ollama 提供 embedding，
      想用它替掉云端的 text-embedding-v3。

  但「换 embedding 模型 = 换整个向量空间」，不能靠感觉切。
  本脚本用**同一套语料 + 同一套用例**，把两个后端各跑一遍，比三件事：

    1. 分辨力：该召回的分数区间 与 不该召回的分数区间，分不分得开；
    2. 最佳阈值：是否存在「误召=0 且 漏召=0」的阈值；
    3. 延迟：单条 embedding 的耗时（本地值取决于你的局域网与 GPU）。

用法：
    # 只测云端（基线）
    .venv/bin/python eval_embedding_compare.py dashscope

    # 两个都测（本地需先起 Ollama 并放行局域网）
    .venv/bin/python eval_embedding_compare.py dashscope ollama

    # 只测本地
    .venv/bin/python eval_embedding_compare.py ollama

环境变量：
    OLLAMA_HOST_URL=http://192.168.x.x:11434   # 本地主机地址
    OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b    # 本地 embedding 模型

⚠️ 它用独立的 chroma_data_eval/ 目录 + 按后端区分的集合，不碰真实记忆库。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from dotenv import load_dotenv

from agent.embedding_backends import get_backend
from agent.memory import MemoryStore
from eval_memory_recall import MEMORIES, CASES, THRESHOLDS

load_dotenv()

EVAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data_eval")


def build_store(backend):
    """按后端建一个独立的评测记忆库（每次重建，保证两边条件一致）。"""
    store = MemoryStore(
        top_k=4,
        backend=backend,
        chroma_dir=EVAL_DIR,
    )
    store.clear()
    for text, kind in MEMORIES:
        store.add(text, {"type": kind})
    return store


def rmse(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.sqrt(((a - b) ** 2).mean()))


def run_backend(backend) -> dict:
    """跑一个后端，返回质量与延迟指标。"""
    print("\n" + "=" * 70)
    print(f"🔬 后端：{backend.name}  模型：{getattr(backend, 'model', '?')}")
    print("=" * 70)

    ok, msg = backend.health()
    if not ok:
        print(f"   ❌ 不可用：{msg}")
        return {"name": backend.name, "ok": False, "error": msg}

    # ---- 延迟（单条 embedding，冷启动后测 5 次取中位）----
    backend.embed("预热")                      # 预热，排除首次建连开销
    lats = []
    for _ in range(5):
        t0 = time.time()
        backend.embed("这是一条用于测量延迟的中文句子，长度约二十字")
        lats.append((time.time() - t0) * 1000)
    latency = float(np.median(lats))

    store = build_store(backend)
    print(f"   📚 建库完成：{store.count()} 条")

    # ---- 逐条 query，记录分数分布 ----
    hit_scores, miss_best = [], []      # 该召回的命中分 / 不该召回的最高分
    rows = []
    for case in CASES:
        q, expect = case["query"], case["expect"]
        # ⚠️ 必须显式 min_score=0.0：search 默认带 0.6 过滤，
        #    否则负例被提前滤掉，阈值扫描就变成「自证完美」的假结论。
        res = store.search(q, top_k=len(MEMORIES), min_score=0.0)
        scored = []
        for r in res:
            idx = next((i for i, (t, _) in enumerate(MEMORIES) if t == r["text"]), -1)
            scored.append((idx, r["score"]))
        rows.append((expect, scored))

        if expect is None:
            if scored:
                miss_best.append(max(s for _, s in scored))
        else:
            s = next((s for i, s in scored if i == expect), None)
            if s is not None:
                hit_scores.append(s)

    # ---- 阈值扫描 ----
    scan = []
    for th in THRESHOLDS:
        ok_n = miss = fp = 0
        for expect, scored in rows:
            kept = [i for i, s in scored if s >= th]
            if expect is None:
                if kept:
                    fp += 1
                else:
                    ok_n += 1
            else:
                if expect in kept:
                    ok_n += 1
                else:
                    miss += 1
        scan.append({"th": th, "ok": ok_n, "miss": miss, "fp": fp,
                     "rate": ok_n / len(rows)})

    perfect = [s for s in scan if s["miss"] == 0 and s["fp"] == 0]
    # 同一「判对」数下，优先要**更严格**的阈值（误召风险更小）
    best = max(scan, key=lambda s: (s["ok"], s["th"]))

    hit_lo = min(hit_scores) if hit_scores else None
    miss_hi = max(miss_best) if miss_best else None
    gap = (hit_lo - miss_hi) if (hit_lo is not None and miss_hi is not None) else None

    print(f"   ⏱️  单条 embedding 延迟（中位）：{latency:.1f} ms")
    if hit_lo is not None:
        print(f"   ✅ 该召回组分数：{hit_lo:.4f} ~ {max(hit_scores):.4f}")
    if miss_hi is not None:
        print(f"   ⚠️  不该召回组最高分：{miss_hi:.4f}")
    if gap is not None:
        print(f"   📏 两组空档：{gap:+.4f}"
              f"{'（可分）' if gap > 0 else '（重叠！分不开）'}")
    print(f"   🎯 最佳阈值 {best['th']:.2f} → 判对 {best['ok']}/{len(rows)}"
          f"（漏召 {best['miss']}，误召 {best['fp']}）")
    if perfect:
        print(f"   ✨ 存在完美阈值：{[round(p['th'], 2) for p in perfect]}")

    return {
        "name": backend.name, "ok": True, "latency": latency,
        "hit_lo": hit_lo, "hit_hi": max(hit_scores) if hit_scores else None,
        "miss_hi": miss_hi, "gap": gap, "best": best, "perfect": perfect,
        "scan": scan,
        # 留一份向量样本，用于算两个后端的「向量空间差异」
        "sample": backend.embed("向量数据库可以实现语义搜索"),
    }


def main():
    names = sys.argv[1:] or ["dashscope", "ollama"]
    results = []
    for n in names:
        try:
            backend = get_backend(n)
        except Exception as e:
            print(f"\n⚠️ 跳过 {n}：{e}")
            continue
        results.append(run_backend(backend))

    usable = [r for r in results if r.get("ok")]
    if len(usable) < 2:
        if usable:
            print("\n（只测了一个后端，跳过对比。要对比请把两个后端都跑通。）")
        return

    print("\n" + "=" * 70)
    print("📊 对比汇总")
    print("=" * 70)
    print(f"{'后端':<12}{'延迟':>10}{'空档':>10}{'最佳阈值':>10}{'判对':>8}{'完美阈值':>10}")
    print("-" * 70)
    for r in usable:
        gap = f"{r['gap']:+.4f}" if r["gap"] is not None else "n/a"
        pf = ",".join(f"{p['th']:.2f}" for p in r["perfect"]) or "无"
        print(f"{r['name']:<12}{r['latency']:>8.1f}ms{gap:>10}"
              f"{r['best']['th']:>10.2f}{r['best']['ok']:>8}{pf:>10}")

    # 向量空间差异：说明「为什么不能混用」
    if len(usable) == 2:
        same_text = "向量数据库可以实现语义搜索"
        v1 = usable[0]["sample"]
        v2 = usable[1]["sample"]
        cos = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        print(f"\n🔎 同一句话在两个后端的向量：cosine 相似度 = {cos:.4f}，"
              f"逐元素 RMSE = {rmse(v1, v2):.4f}")
        print("    → 两种向量**不在同一个空间**，绝不能混进同一张表检索。")

    print("\n💡 怎么决策：")
    print("   1. 先看『空档』：本地是否为正值且与云端接近？差距大就别换；")
    print("   2. 再看『判对/完美阈值』：本地若能找到完美阈值，说明质量够用；")
    print("   3. 最后才看延迟：它是加分项，不是决策项（云端本来就不慢）。")


if __name__ == "__main__":
    main()
