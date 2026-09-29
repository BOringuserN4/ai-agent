# -*- coding: utf-8 -*-
"""
eval_embedding_v4.py — 换更强 embedding 的 A/B（2026/09/29）

要回答的问题：
  2026/09/23 发现召回断层——「我的职业是什么？」对记忆
  「用户是一名测试开发工程师」相似度仅 0.5051（< 阈值 0.6），召不回。
  09/29 用「文本增富」改善到 0.6690，但**口语化问法仍失败**（0.420）。

  本脚本检验候选 1：**换更强的 embedding 模型**能否根治。

=== 对比三个配置 ===
  甲 · text-embedding-v3 @1024（现状）
  乙 · text-embedding-v4 @1024（同维度，可复用旧集合结构）
  丙 · text-embedding-v4 @2048（更强，但维度变了）

=== 关键指标：空档（gap）===
  该召回组的**最低分** − 不该召回组的**最高分**
  · gap > 0 → 两组可分，存在一个万能阈值
  · gap ≤ 0 → 重叠，单靠阈值救不了（正是 09/23 遇到的情况）

  按 skill 的要点：**必须用 min_score=0.0 拿未过滤的完整分布**，
  否则 search() 默认的 0.6 过滤会滤掉负例，让阈值扫描「自证完美」。

用法：.venv/bin/python eval_embedding_v4.py
"""
import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from agent.embedding_backends import DashScopeBackend
from agent.memory import MemoryStore
from agent.extractor import build_embed_text

# ---- 语料：3 条记忆（覆盖 mem1/mem2/mem3 三类事实）----
MEMORIES = [
    {"text": "用户是一名测试开发工程师",
     "questions": ["我是做什么工作的", "我的职业是什么", "我是干啥的"]},
    {"text": "用户养了一只猫，名字叫豆豆",
     "questions": ["我家猫叫什么", "我养了什么宠物"]},
    {"text": "用户偏好用 Python 而不是 Java 写脚本",
     "questions": ["我喜欢用什么语言", "我的语言偏好"]},
]

# ---- 该召回（含**留出**：留出项没写进 questions，用来防自我循环）----
POSITIVE = [
    ("我的职业是什么？", 0, False),
    ("我做什么工作？", 0, False),
    ("我是谁？", 0, True),                    # 留出
    ("你还记得我干什么的吗", 0, True),          # 留出
    ("我干啥的来着", 0, True),                 # 留出（09/29 曾失败）
    ("介绍一下你是跟谁在说话", 0, True),        # 留出（09/29 曾失败）
    ("我的猫叫什么", 1, False),
    ("我养的那只动物名字", 1, True),            # 留出
    ("我喜欢用什么语言", 2, False),
    ("我更习惯用哪门语言", 2, True),            # 留出
]

# ---- 不该召回 ----
# ⚠️ 分两档（2026/09/29 修正）：
#   第一版只用了「明显无关」的负例（最高才 0.4274），结论会**虚高**。
#   真正的考验来自**难负例**——2026/09/14 测得这类会落到 0.444~0.515，
#   与「该召回」组**重叠**，造成单靠阈值救不了的困境。
NEGATIVE_EASY = [
    "上海天气怎么样",
    "帮我算 123*456",
    "推荐一部电影",
    "现在几点了",
    "帮我写个快速排序",
]
NEGATIVE_HARD = [
    "介绍一下华为公司的计算业务",      # 通用知识（09/14 难负例）
    "什么是向量数据库？",             # 通用知识
    "英伟达当前的计算业务怎么样",       # 通用知识
    "解释一下什么是大语言模型",         # 通用知识
    "机器学习和深度学习的区别",         # 通用知识
]


def make_store(model: str, dim: int):
    """建一个指定模型/维度的独立库。"""
    d = tempfile.mkdtemp(prefix=f"v4_{model}_{dim}_")
    backend = DashScopeBackend(model=model)
    backend.dim = dim                     # 覆盖类属性维度
    store = MemoryStore(chroma_dir=d, backend=backend)
    # 目录不同已足够隔离；collection 名再带上模型维度，双保险
    store.collection_name = f"m_{model}_{dim}"
    store.collection = store._chroma.get_or_create_collection(
        name=store.collection_name, metadata={"hnsw:space": "cosine"})
    store.clear()
    for item in MEMORIES:
        store.add(item["text"], {"type": "test"},
                  embed_text=build_embed_text(item["text"], item["questions"]))
    return store


def run(model: str, dim: int, label: str):
    store = make_store(model, dim)

    # 延迟（热态，取 5 次中位）
    store.backend.embed("预热")
    lats = []
    for _ in range(5):
        t0 = time.time()
        store.backend.embed("一条用于测延迟的中文句子")
        lats.append((time.time() - t0) * 1000)
    lat = statistics.median(lats)

    pos_scores, pos_rows = [], []
    for q, tgt, holdout in POSITIVE:
        r = store.search(q, top_k=len(MEMORIES), min_score=0.0)
        top = r[0] if r else None
        idx = next((i for i, m in enumerate(MEMORIES)
                    if top and m["text"] == top["text"]), -1)
        s = top["score"] if top else 0.0
        ok = (idx == tgt and s >= 0.6)
        pos_scores.append(s)
        pos_rows.append((q, tgt, idx, s, ok, holdout))

    neg_easy, neg_hard = [], []
    for q in NEGATIVE_EASY:
        r = store.search(q, top_k=len(MEMORIES), min_score=0.0)
        neg_easy.append(r[0]["score"] if r else 0.0)
    for q in NEGATIVE_HARD:
        r = store.search(q, top_k=len(MEMORIES), min_score=0.0)
        neg_hard.append(r[0]["score"] if r else 0.0)
    neg_scores = neg_easy + neg_hard

    print(f"\n{'=' * 76}\n🔬 {label}（{model} @{dim}维）\n{'=' * 76}")
    print(f"{'问法':<24}{'期望':<6}{'实际':<6}{'分数':>8}{'过阈值':>8}  备注")
    print("-" * 76)
    for q, tgt, idx, s, ok, ho in pos_rows:
        note = "留出" if ho else ""
        print(f"{q[:22]:<24}#{tgt:<5}#{idx:<5}{s:>8.4f}{'✅' if ok else '❌':>8}  {note}")
    print("-" * 76)
    print(f"{'不该召回的（易）':<26}{'':<12}{'分数':>8}")
    for q, s in zip(NEGATIVE_EASY, neg_easy):
        print(f"  {q[:24]:<24}{'':<12}{s:>8.4f}")
    print(f"{'不该召回的（难）':<26}{'':<12}")
    for q, s in zip(NEGATIVE_HARD, neg_hard):
        print(f"  {q[:24]:<24}{'':<12}{s:>8.4f}{'  ⚠️ 难负例' if s >= 0.45 else ''}")
    print("-" * 76)

    pos_min = min(pos_scores)
    neg_max = max(neg_scores)
    gap = pos_min - neg_max
    # 推荐阈值 = 空档中点（gap>0 时它能让该召回全过、不该召回全不触发）
    thr = (pos_min + neg_max) / 2 if gap > 0 else None
    n_ho = sum(1 for *_, ok, ho in pos_rows if ho)
    n_ho_ok = sum(1 for q, t, i, s, ok, ho in pos_rows if ho and ok)

    # 在该阈值下的表现
    if thr is not None:
        pos_pass = sum(1 for s in pos_scores if s >= thr)
        neg_fire = sum(1 for s in neg_scores if s >= thr)
    else:
        pos_pass = neg_fire = None

    print(f"该召回组：最低 {pos_min:.4f}｜最高 {max(pos_scores):.4f}")
    print(f"不该召回：最高 {neg_max:.4f}（其中难负例最高 "
          f"{max(neg_hard) if neg_hard else 0:.4f}）")
    print(f"**空档 gap：{gap:+.4f}**  {'✅ 可分' if gap > 0 else '❌ 重叠（阈值救不了）'}")
    if thr is not None:
        print(f"推荐阈值 = 中点 {thr:.4f} → 该召回 {pos_pass}/{len(pos_scores)} 过，"
              f"不该召回 {neg_fire} 条误触发")
    print(f"（固定阈值 0.6 下：{sum(1 for *_, ok, _ in pos_rows if ok)}/{len(pos_rows)} 过）")
    print(f"**留出集命中**：{n_ho_ok}/{n_ho}")
    print(f"单条延迟（中位）：{lat:.0f} ms")

    return {"label": label, "model": model, "dim": dim, "lat": lat,
            "pos_min": pos_min, "pos_max": max(pos_scores), "neg_max": neg_max,
            "neg_hard_max": max(neg_hard) if neg_hard else 0,
            "gap": gap, "thr": thr, "pos_pass": pos_pass, "neg_fire": neg_fire,
            "ok": sum(1 for *_, ok, _ in pos_rows if ok), "total": len(pos_rows),
            "ho_ok": n_ho_ok, "ho_total": n_ho}


def main():
    print("=" * 76)
    print("🔬 换更强 embedding 的 A/B（指标：空档 gap 与留出集命中）")
    print("=" * 76)
    print("留出 = 该问法**没写进 questions**，用于防「拿测试集调参」的自我循环\n")

    rows = []
    for model, dim, label in (
        ("text-embedding-v3", 1024, "甲 · 现状"),
        ("text-embedding-v4", 1024, "乙 · 换 v4（同维度）"),
        ("text-embedding-v4", 2048, "丙 · 换 v4（2048维）"),
    ):
        rows.append(run(model, dim, label))

    print("\n" + "=" * 76)
    print("📊 汇总")
    print("=" * 76)
    print(f"{'配置':<20}{'空档':>9}{'难负例最高':>11}{'推荐阈值':>10}"
          f"{'该召回':>9}{'留出':>8}{'延迟':>8}")
    print("-" * 80)
    for r in rows:
        thr = f"{r['thr']:.3f}" if r["thr"] is not None else "n/a"
        print(f"{r['label']:<20}{r['gap']:>+9.4f}{r['neg_hard_max']:>11.4f}"
              f"{thr:>10}{str(r['pos_pass']) + '/' + str(r['total']):>9}"
              f"{str(r['ho_ok']) + '/' + str(r['ho_total']):>8}"
              f"{str(round(r['lat'])) + 'ms':>8}")
    print("-" * 80)

    best = max(rows, key=lambda r: (r["gap"], r["ho_ok"]))
    print(f"\n最优：{best['label']}（空档 {best['gap']:+.4f}，留出命中 {best['ho_ok']}/{best['ho_total']}）")

    print("\n怎么读：")
    print("  · **空档 gap** 是最硬的指标：>0 才说明「该召回」与「不该召回」真能分开")
    print("  · **难负例**决定 gap 是否可信：只用易负例会高估效果（第一版就犯了这错）")
    print("  · **留出命中**是关键：只有它才能证明提升不是「照抄测试问法」的结果")
    print("  · 维度变了（2048）表示向量空间不同 → 必须重建库，不能混用")


if __name__ == "__main__":
    main()
