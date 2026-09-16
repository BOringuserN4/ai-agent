# -*- coding: utf-8 -*-
"""eval_evaluator_critic.py — Evaluator-Critic 正反例对比实验（2026/09/16）

目的：用同一套 Evaluator-Critic 跑两个任务，拿出发给「该不该用这个模式」的实测账。

  - 正例（POSITIVE_TASK）：约束明确、批判能挑出错、挑错后确实改得动
      → 期望：某轮达标后停止，分数曲线上扬
  - 反例（NEGATIVE_TASK）：命中否决线④（无法从批判中改进，缺的是信息）
      → 期望：轮轮批、轮轮不改，分数曲线走平，token 白烧

产出：每轮的分数 + 两组的 token 用量对照。
用法：.venv/bin/python eval_evaluator_critic.py
"""
import sys
import time

from agent.evaluator_critic import EvaluatorCritic, POSITIVE_TASK, NEGATIVE_TASK

# 及格线：85 = 合规 + 手艺分约 6.3/10，是「能用」的水平；
# 90 以上属于「生产精品」要求，实测会诱发「为凑手艺分而破坏硬约束」的回退（见 --strict）
POS_THRESHOLD = 85
NEG_THRESHOLD = 85
STRICT_THRESHOLD = 90


def run_case(name: str, task: str, threshold: int = 85, max_rounds: int = 3) -> dict:
    print("\n" + "#" * 60)
    print(f"# 场景：{name}")
    print("#" * 60)
    ec = EvaluatorCritic(threshold=threshold, max_rounds=max_rounds)
    t0 = time.time()
    result = ec.run(task)
    result["elapsed_s"] = round(time.time() - t0, 1)
    return result


def main():
    strict = "--strict" in sys.argv
    if strict:
        run_case(f"追加实拍 · 及格线拧到 {STRICT_THRESHOLD}（虚高）",
                 POSITIVE_TASK, threshold=STRICT_THRESHOLD)

    pos = run_case("正例 · 可挑错且可改好（硬约束文案）", POSITIVE_TASK,
                   threshold=POS_THRESHOLD)
    neg = run_case("反例 · 无法从批判中改进（缺信息）", NEGATIVE_TASK,
                   threshold=NEG_THRESHOLD)

    print("\n" + "=" * 60)
    print("📊 对照结论")
    print("=" * 60)
    header = f"{'场景':<24}{'轮次':>6}{'分数轨迹':>16}{'token':>10}{'耗时':>8}"
    print(header)
    print("-" * 60)
    for label, r in (("正例 · 可改好", pos), ("反例 · 缺信息", neg)):
        curve = " → ".join(str(h["score"]) for h in r["history"])
        print(f"{label:<24}{r['rounds']:>6}{curve:>16}"
              f"{r['usage']['total']:>10}{str(r['elapsed_s']) + 's':>8}")
    print("-" * 60)
    print(f"正例最终：第 {pos['rounds']} 轮，{pos['final_score']} 分，"
          f"{'达标 ✅' if pos['passed'] else '未达标 ✗'}")
    print(f"反例最终：第 {neg['rounds']} 轮，{neg['final_score']} 分，"
          f"{'达标 ✅' if neg['passed'] else '未达标 ✗'}")
    saved = neg["usage"]["total"] - pos["usage"]["total"]
    print(f"\n💡 反例比正例{'多' if saved > 0 else '少'}烧 {abs(saved)} token，"
          f"但质量没有任何提升——这就是否决线④的代价。")


if __name__ == "__main__":
    main()
