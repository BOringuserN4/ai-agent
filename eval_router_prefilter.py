# -*- coding: utf-8 -*-
"""
eval_router_prefilter.py — Router 规则预筛对照实验（2026/09/22）

目的：量出「规则预筛」在真实用例上的收益，并检查它是否**安全**。

=== 两组对比 ===

  甲 · 无预筛：每条都问 Router（改造前行为）
  乙 · 有预筛：规则判「明显不用拆」的直接走 solo，跳过 Router

=== 三个指标 ===

  1. **token**：预筛省下的就是 Router 那笔（实测约 450 token/次）
  2. **跳过率**：多少条查询被规则拦下（不问 Router）
  3. **答对率**：⚠️ 这条最重要——预筛有没有把任务搞坏

=== 安全判据（本章的核心）===

  本项目两种误判后果不对称：
    Router 误判「不拆」 → 降级（solo 接得住，慢/贵一点）
    工具漏选           → 硬失败（工具不存在）
  ⇒ 所以预筛的风险是「退化」不是「崩溃」。
  但**仍要实测确认**：预筛跳过的那些题，答案有没有变差。

用法：.venv/bin/python eval_router_prefilter.py
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.multi_agent import MultiAgent
from agent.golden_set import GOLDEN_SET

REPEATS = 1   # 全量跑 14 题，每题 1 次即可（token 差异远大于抖动）


def _zero(ma):
    for w in ma.experts.values():
        w.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for a in (ma.router, ma.merger):
        a.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _total(ma):
    return (sum(w.usage["total_tokens"] for w in ma.experts.values())
            + ma.router.usage["total_tokens"] + ma.merger.usage["total_tokens"])


def _answer_ok(case, answer: str) -> bool:
    """粗判答对：expected 里的关键数字/词是否出现（确定性，不用 LLM 判）。"""
    if not answer:
        return False
    exp = str(case.get("expected", ""))
    nums = re.findall(r"-?\d+\.?\d*", exp)
    if nums:
        return all(n in answer for n in nums[:2])
    # 无数字的题：看答案非空且不太短（避免空回答算通过）
    return len(answer.strip()) > 10


def run_group(use_prefilter: bool, label: str):
    print("\n" + "#" * 74)
    print(f"# {label}（预筛 {'开' if use_prefilter else '关'}）")
    print("#" * 74)
    print(f"{'用例':<34}{'Router':>8}{'专家':>7}{'合计':>7}{'跳过':>6}{'答对':>6}")
    print("-" * 74)

    total_tok = 0
    skipped = 0
    ok_cnt = 0
    rows = []
    for c in GOLDEN_SET:
        ma = MultiAgent(use_memory=False)
        if not use_prefilter:
            ma.prefilter = None          # 关闭预筛 = 改造前行为
        _zero(ma)
        ans = ma.run(c["input"])
        rt = ma.router.usage["total_tokens"]
        st = sum(w.usage["total_tokens"] for w in ma.experts.values())
        mt = ma.merger.usage["total_tokens"]
        tok = rt + st + mt
        did_skip = (rt == 0)
        ok = _answer_ok(c, ans)
        total_tok += tok
        skipped += did_skip
        ok_cnt += ok
        rows.append((c, tok, did_skip, ok))
        print(f"{c['input'][:32]:<34}{rt:>8}{st:>7}{tok:>7}"
              f"{'⏭️' if did_skip else '':>6}{'✅' if ok else '❌':>6}")
    print("-" * 74)
    print(f"合计 token {total_tok}｜跳过 {skipped}/{len(GOLDEN_SET)}"
          f"｜答对 {ok_cnt}/{len(GOLDEN_SET)}")
    return {"token": total_tok, "skipped": skipped, "ok": ok_cnt, "rows": rows}


def main():
    print("=" * 74)
    print("🔬 Router 规则预筛 · 对照实验")
    print("=" * 74)
    print(f"语料：golden_set 共 {len(GOLDEN_SET)} 条（含 math/weather/general/edge 四类）")

    base = run_group(False, "甲 · 无预筛")
    opt = run_group(True, "乙 · 有预筛")

    print("\n" + "=" * 74)
    print("📊 对照结论")
    print("=" * 74)
    print(f"{'组别':<14}{'总 token':>10}{'跳过':>8}{'答对':>8}")
    print("-" * 74)
    print(f"{'甲 · 无预筛':<14}{base['token']:>10}{base['skipped']:>8}{base['ok']:>8}")
    print(f"{'乙 · 有预筛':<14}{opt['token']:>10}{opt['skipped']:>8}{opt['ok']:>8}")
    print("-" * 74)

    saved = base["token"] - opt["token"]
    pct = saved / max(base["token"], 1) * 100
    print(f"\n省下：**{saved} token（{pct:.1f}%）**")
    print(f"跳过率：{opt['skipped']}/{len(GOLDEN_SET)}"
          f" = {opt['skipped']/len(GOLDEN_SET):.0%}")
    print(f"答对：{base['ok']} → {opt['ok']}"
          f"（{'✅ 未退化' if opt['ok'] >= base['ok'] else '⚠️ 出现退化，需排查'}）")

    # 逐条差异
    print("\n逐条 token 差（乙 − 甲）：")
    for (cb, tb, _, _), (co, to, sk, _) in zip(base["rows"], opt["rows"]):
        d = to - tb
        flag = "⏭️ 跳过 Router" if sk else ""
        print(f"  {co['input'][:30]:<32} {d:>+6}  {flag}")

    print("\n怎么读：")
    print("  · 被跳过的题，省下的正好是一整次 Router 调用")
    print("  · 没被跳过的题，token 差异应≈0（走了同一条路，变化是噪声）")
    print("  · **答对率是安全线**：预筛若让答对率下降，说明规则太激进")


if __name__ == "__main__":
    main()
