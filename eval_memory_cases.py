# -*- coding: utf-8 -*-
"""
eval_memory_cases.py — 记忆用例评测（收尾章，2026/09/23）

要补的那个「缝」：

  项目里原来有两套评测，各测各的：
    · eval_memory_recall.py —— 测**召回分数**（向量检索准不准），绕过了 Agent
    · eval_runner.py        —— 测**端到端回答**，但完全不测记忆
  中间缺一环：「**该想起的事，Agent 到底想起来没有？**」

  记忆链路的五个环节：
    ① 存进库里 → ② 检索召回 → ③ 注入 context → ④ 模型用了它 → ⑤ 答出来
  eval_memory_recall 只测到 ②，而用户看到的是 ⑤。
  本脚本把评测补到 ⑤ 这一端。

=== 关键设计：对照实验 ===

  每条用例跑**两遍**：
    甲 · 有记忆（种入 seed 后跑）
    乙 · 无记忆（同题，但库里空着）
  看两遍的差别 —— **那才是记忆的真实贡献**。

  为什么要这个对照：有些题**不靠记忆也能答对**（模型可能猜中），
  单看甲组会把「本来就答得对」误算成「记忆起作用了」。

=== 三个判据（全部确定性，不用 LLM judge）===

  1. must_recall     答案必须**出现**的关键事实（只有记忆里才有）
  2. must_not        答案里**不该出现**的内容（防被无关记忆带偏）
  3. must_not_gold   特殊项：记忆里没有时，**不该编造**

用法：
    .venv/bin/python eval_memory_cases.py

⚠️ 用独立的 chroma_data_memcases/ 目录，不碰真实记忆库；
   且每条用例跑完**必清库**（见 golden_set.MEMORY_CASES 的注释）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent.memory as mem_mod
from agent.core import Agent
from agent.extractor import build_embed_text
from agent.golden_set import MEMORY_CASES

# 独立目录：与真实库（chroma_data）、召回评测库（chroma_data_eval）都不共用
EVAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "chroma_data_memcases")
COLLECTION = "memory_memcases"


def build_store():
    """建一个专用记忆库（评测用，跑完即清）。

    隔离靠**目录**，不靠改 collection 名：
      MemoryStore._sync_collection() 会按后端推导 collection 名，
      手工覆盖 collection_name 会被它覆盖回去（无意义）。
      目录不同（chroma_data_memcases/ ≠ chroma_data/）就足够隔离。
    """
    store = mem_mod.MemoryStore(chroma_dir=EVAL_DIR)
    store.clear()
    return store


# 对冲词：表示「我不知道 / 没有相关信息」的说法
HEDGES = ["不知道", "没有关于", "没有相关", "无法", "没提到", "没有记录",
          "未提及", "不清楚", "未提供", "抱歉", "不好意思", "没有保存",
          "不在我", "记不得了"]


def judge(case: dict, answer: str) -> tuple:
    """确定性判据。返回 (是否通过, 说明)。

    四道判据（关键在于第 4 条，它是「记忆真的起作用」的判据）：

      1. must_recall     答案必须出现的关键事实（只有记忆里才有）
      2. must_not        答案里不该出现的内容（防被无关记忆带偏）
      3. must_not_gold   记忆里没有时，不该编造（应说不知道）
      4. **对冲词规则**：
         · 有 seed 的题 → 答案**不该**说「不知道」
           （说了 = 记忆没送到，或模型没用它）
         · 无 seed 的题 → 答案**该**说「不知道」
         这条解决了 mem3 那类「模型把答案里的示例词当成命中」的误判：
         无记忆时模型答「不知道…比如 Python、Bash」，含 Python 但加了引号列举，
         靠第 4 条即可判出它没真用记忆。
    """
    a = answer or ""
    has_hedge = any(h in a for h in HEDGES)
    seeded = bool(case.get("seed"))

    if case.get("must_recall") and case["must_recall"] not in a:
        return False, f"未答出「{case['must_recall']}」"

    if case.get("must_not") and case["must_not"] in a:
        return False, f"被无关记忆带偏（出现了「{case['must_not']}」）"

    if case.get("must_not_gold") and not has_hedge:
        return False, "记忆里没有该信息，却给出了肯定答复（疑似编造）"

    # 判据 4：对冲词规则（有 seed 不该说不知道；无 seed 该说不知道）
    if seeded and not case.get("must_not"):
        if has_hedge:
            return False, "有记忆却称「不知道」（记忆未送达/未被采用）"
    if not seeded and not case.get("must_not") and not case.get("must_not_gold"):
        if not has_hedge:
            return False, "无记忆却给出肯定答复"

    return True, "通过"


def run_case(case: dict, use_memory: bool) -> dict:
    """按「有无记忆」两种条件跑一条用例。"""
    store = build_store()
    store.clear()
    if use_memory and case.get("seed"):
        for item in case["seed"]:
            # 走与生产一致的路径：存储用精简 text，向量化用增富文本
            # （事实 + 可能被怎么问），提高召回率但不增加注入 token。
            embed_src = build_embed_text(item["text"], item.get("questions"))
            store.add(item["text"], item.get("meta"), embed_text=embed_src)

    agent = Agent(
        system_prompt="你是一个乐于助人的助手。若有相关历史记忆，请优先依据记忆回答。",
        tools=None,
        memory=store if (use_memory and case.get("seed")) else None,
    )
    t0 = time.time()
    try:
        answer = agent.run(case["input"])
    except Exception as e:
        answer = f"<ERROR {type(e).__name__}: {e}>"
    elapsed = round(time.time() - t0, 2)

    recalled = []
    if use_memory and case.get("seed"):
        recalled = [r["text"] for r in store.search(case["input"])]

    store.clear()            # ⚠️ 必须清：防上一条用例的记忆污染下一条
    ok, why = judge(case, answer)
    return {"answer": answer, "ok": ok, "why": why,
            "elapsed": elapsed, "recalled": recalled,
            "tokens": agent.usage["total_tokens"]}


def main():
    print("=" * 76)
    print("🧠 记忆用例评测（收尾章）")
    print("=" * 76)
    print(f"用例 {len(MEMORY_CASES)} 条｜每条跑两遍（有记忆 / 无记忆）作对照")
    print("判据：must_recall（必须答出）｜must_not（不该带偏）｜must_not_gold（不该编）\n")

    rows = []
    for c in MEMORY_CASES:
        with_mem = run_case(c, use_memory=True)
        no_mem = run_case(c, use_memory=False)
        rows.append((c, with_mem, no_mem))

        tag = " / ".join(c.get("tags", []))
        print(f"{'─' * 76}")
        print(f"[{c['id']}] {c['input']}   （{tag}）")
        print(f"  seed: {[s['text'][:24] for s in c.get('seed', [])] or '（空）'}")
        gap = c.get("known_gap")
        print(f"  有记忆: {'✅' if with_mem['ok'] else '❌'} {with_mem['why']}"
              f" | 召回 {len(with_mem['recalled'])} 条"
              f"{'  ⚠️ 已知缺口' if gap else ''}")
        if gap and not with_mem["ok"]:
            print(f"     ↳ {gap}")
        print(f"     └ {with_mem['answer'][:96]}")
        print(f"  无记忆: {'✅' if no_mem['ok'] else '❌'} {no_mem['why']}")
        print(f"     └ {no_mem['answer'][:96]}")

    # ---- 汇总 ----
    print("\n" + "=" * 76)
    print("📊 汇总")
    print("=" * 76)
    print(f"{'ID':<8}{'有记忆':<8}{'无记忆':<8}{'记忆贡献':<10}{'说明'}")
    print("-" * 76)
    contrib_cnt = 0
    for c, w, n in rows:
        # 「记忆贡献」= 有记忆时通过、无记忆时不通过 → 说明记忆真的起了作用
        contrib = w["ok"] and not n["ok"]
        contrib_cnt += contrib
        print(f"{c['id']:<8}{'✅' if w['ok'] else '❌':<8}"
              f"{'✅' if n['ok'] else '❌':<8}"
              f"{'✓ 有贡献' if contrib else '—':<10}"
              f"{(w['why'] if not w['ok'] else '')[:30]}")
    print("-" * 76)

    w_ok = sum(1 for _, w, _ in rows if w["ok"])
    n_ok = sum(1 for _, _, n in rows if n["ok"])
    print(f"有记忆通过：{w_ok}/{len(rows)}")
    print(f"无记忆通过：{n_ok}/{len(rows)}")
    print(f"**记忆确有贡献的用例：{contrib_cnt} 条**"
          f"（有记忆通过、无记忆不通过）")

    print("\n怎么读：")
    print("  · '有记忆 ✅ / 无记忆 ❌' —— 这才是记忆在起作用的证据")
    print("  · '两边都 ✅' —— 说明这题不靠记忆也能答对，**验证不了记忆**（题出得太松）")
    print("  · '两边都 ❌' —— 记忆没用上，或判据太严，需排查")
    print("  · mem4/mem5 是干扰与反向题：考验'不被带偏'与'不编造'")

    tot = sum(w["tokens"] + n["tokens"] for _, w, n in rows)
    print(f"\n总 token：{tot}（每条跑两遍）")


if __name__ == "__main__":
    main()
