# -*- coding: utf-8 -*-
"""
eval_runner.py — 评测跑批入口（2026/09/10）

职责：把「Golden Set + 被测 Agent + LLM-as-Judge」串起来，跑一轮完整评测。

流程（6 步，对应大纲 7.5）：
  1. 载入评测数据集（agent/golden_set.py）
  2. 逐条送进被测 Agent（本项目的 Multi-Agent Router）
  3. 记录 Agent 输出 + 耗时 + token 用量
  4. LLM-as-Judge 打分（agent/judge.py）
  5. 汇总：总分均值 / 通过率 / 分类统计
  6. 落盘 JSON 报告 + 终端表格

本轮评测的三条关键决策（2026/09/10 定）：
  ① 长期记忆 = 关（use_memory=False）
     理由：开记忆会让第 N 题被前面题目的"记忆"污染 → 分数随执行顺序漂移、
     不可复现，且 embedding 耗时混入 elapsed_ms。评测 = 闭卷考试，起点必须一致。
  ② Agent 报错 = 整轮中断（fail-fast）
     理由：评测环境的异常往往意味着环境本身坏了（API key 失效 / 网络断），
     继续跑下去只会产出一堆脏数据。**但中断前会先落盘已完成的部分结果**，
     避免白跑。见 _run_agent_cases 的 except 分支。
  ③ 单条题 = 最多 2 次机会（首次不过才重试）
     理由：Agent 有随机性（temperature=0.3），单次失败可能是抖动而非真实能力差。
     首次通过 → 只跑 1 次；首次不过 → 再来 1 次，取**较好成绩**为本条最终分。
     ⚠️ 注意：best-of-2 会**抬高**整体分数、掩盖不稳定性，所以报告里单独记录
     "retried" 条数，方便你判断分数里有多少是"重试捞回来的"。

用法：
  python eval_runner.py                    # 跑全部 13 条
  python eval_runner.py --limit 3          # 只跑前 3 条（快速自检）
  python eval_runner.py --langfuse         # 额外把评测同步到 Langfuse（Experiment）
  python eval_runner.py --compare a.json b.json   # 对比两份报告

设计要点：
  - 报告落盘到 eval_reports/，文件名带时间戳 → 天然版本化，可回归对比。
  - 默认不依赖 Langfuse（本地可跑）；--langfuse 时才上报。
"""
import argparse
import json
import os
import time
from datetime import datetime

from agent.golden_set import GOLDEN_SET, categorize
from agent.judge import Judge, DIMENSIONS, is_env_error

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_reports")
PASS_LINE = 60  # 及格线，与 judge.py 保持一致


class AbortEval(RuntimeError):
    """环境级故障时抛出：表示评测环境坏了，整轮中断。

    注意只用于「环境异常」（API key 失效 / 连不上 / 超时），
    不用于「被测表现差」——后者应记录后继续跑。
    """


def _run_one_attempt(agent, case, attempt_no, judge):
    """跑一条题的一次尝试：Agent 出答案 → 裁判打分。返回 attempt dict。"""
    print(f"   ↩ 第 {attempt_no} 次尝试…")
    t0 = time.time()
    try:
        answer = agent.run(case["input"])
    except Exception as e:
        if is_env_error(e):
            # 决策②：环境级异常 = 环境坏了，整轮中断（上层捕获后落盘部分结果）
            raise AbortEval(f"环境级故障，Agent 在 [{case['id']}] 报错：{type(e).__name__}: {e}") from e
        # 普通异常（被测表现差）：记录为一次「失败尝试」，继续跑后面的题
        print(f"   ⚠️ 本题 Agent 报错（非环境级，继续跑）：{type(e).__name__}: {e}")
        return {
            "attempt": attempt_no,
            "answer": None,
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
            "scores": None, "total": None, "compliance": None,
            "pass": False, "reason": "",
            "judge_error": None,
            "agent_error": f"{type(e).__name__}: {e}",
        }
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    verdict = judge.score(
        question=case["input"],
        expected=case["expected"],
        checks=case.get("checks", []),
        answer=answer,
        must_have=case.get("must_have"),
    )
    if verdict.get("env_error"):
        raise AbortEval(f"环境级故障，裁判在 [{case['id']}] 报错：{verdict['error']}")

    mark = "✅" if verdict["pass"] else ("❓" if verdict["pass"] is None else "❌")
    print(f"   {mark} 得分 {verdict['total']} | {verdict['reason'][:50]}")
    return {
        "attempt": attempt_no,
        "answer": answer,
        "elapsed_ms": elapsed_ms,
        "scores": verdict["scores"],
        "total": verdict["total"],
        "compliance": verdict["compliance"],
        "must_have_met": verdict.get("must_have_met"),
        "pass": verdict["pass"],
        "reason": verdict["reason"],
        "judge_error": verdict["error"],
        "agent_error": None,
    }


def _run_case(agent, case, judge, max_attempts=2):
    """跑一条题：决策③ —— 首次不过才重试，最多 max_attempts 次，取较好成绩。"""
    attempts = []
    for i in range(1, max_attempts + 1):
        att = _run_one_attempt(agent, case, i, judge)
        attempts.append(att)
        if att["pass"]:  # 首次通过 → 不再重试
            break
        if i < max_attempts:
            print(f"   ⏳ 未通过，给第 {i + 1} 次机会…")

    # 取"较好成绩"作为本条最终分（best-of-N）
    scored = [a for a in attempts if isinstance(a.get("total"), (int, float))]
    best = max(scored, key=lambda a: a["total"]) if scored else attempts[-1]
    return {
        "id": case["id"],
        "category": case["category"],
        "tags": case.get("tags", []),
        "input": case["input"],
        "expected": case["expected"],
        "checks": case.get("checks", []),
        # 最终成绩（取最好一次）
        "final_answer": best["answer"],
        "final_total": best["total"],
        "final_pass": best["pass"],
        "final_scores": best["scores"],
        "final_reason": best["reason"],
        "must_have_met": best.get("must_have_met"),
        "elapsed_ms_total": round(sum(a["elapsed_ms"] for a in attempts), 1),
        # 过程留痕
        "attempts": attempts,
        "n_attempts": len(attempts),
        "retried": len(attempts) > 1,
        "agent_error": any(a.get("agent_error") for a in attempts),
        "judge_error": any(a.get("judge_error") for a in attempts),
    }


def _run_agent_cases(agent, cases, judge, max_attempts=2):
    """逐条跑被测 Agent，返回结果列表。Agent 报错时落盘部分结果并中断。"""
    results = []
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] 🧪 {case['id']} ({case['category']})：{case['input']}")
        try:
            results.append(_run_case(agent, case, judge, max_attempts))
        except AbortEval as e:
            print(f"\n🛑 整轮中断（决策② fail-fast）：{e}")
            _dump_partial(results, e)
            raise
    return results


def _dump_partial(results, err):
    """中断前把已完成的部分结果落盘，避免白跑。"""
    if not results:
        print("   （还没有完成任何题目，无部分结果可保存）")
        return
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"aborted": True, "error": str(err), "partial_results": results},
                  f, ensure_ascii=False, indent=2)
    print(f"   💾 已完成 {len(results)} 条的部分结果已保存：{path}")


def _summarize(results):
    """汇总：总分均值 / 通过率 / 重试率 / 分类统计。"""
    scored = [r for r in results if isinstance(r.get("final_total"), (int, float))]
    totals = [r["final_total"] for r in scored]
    passed = [r for r in scored if r.get("final_pass")]
    summary = {
        "count": len(results),
        "scored": len(scored),
        "judge_errors": sum(1 for r in results if r.get("judge_error")),
        "agent_errors": sum(1 for r in results if r.get("agent_error")),
        "retried": sum(1 for r in results if r.get("retried")),
        "retry_rescued": sum(1 for r in results if r.get("retried") and r.get("final_pass")),
        "mean_total": round(sum(totals) / len(totals), 1) if totals else None,
        "min_total": min(totals) if totals else None,
        "max_total": max(totals) if totals else None,
        "pass_rate": round(len(passed) / len(scored) * 100, 1) if scored else None,
        "by_category": {},
    }
    for cat in categorize():
        cs = [r for r in scored if r["category"] == cat]
        if cs:
            summary["by_category"][cat] = {
                "n": len(cs),
                "mean_total": round(sum(c["final_total"] for c in cs) / len(cs), 1),
                "pass_rate": round(sum(1 for c in cs if c["final_pass"]) / len(cs) * 100, 1),
            }
    return summary


def _print_summary(summary, results):
    print("\n" + "═" * 60)
    print("📊 评测总结")
    print("═" * 60)
    print(f"  题目数：{summary['count']}   有效评分：{summary['scored']}")
    print(f"  平均总分：{summary['mean_total']}  （区间 {summary['min_total']} ~ {summary['max_total']}）")
    print(f"  通过率  ：{summary['pass_rate']}%   （及格线 {PASS_LINE}）")
    if summary["retried"]:
        print(f"  🔁 重试  ：{summary['retried']} 条触发重试，其中 {summary['retry_rescued']} 条被第 2 次救回")
    if summary["judge_errors"]:
        print(f"  ⚠️ 裁判报错：{summary['judge_errors']} 条")
    if summary["agent_errors"]:
        print(f"  ⚠️ Agent 报错（非环境级）：{summary['agent_errors']} 条")
    print("\n  分类得分：")
    for cat, s in summary["by_category"].items():
        print(f"    - {cat:8s} n={s['n']:2d}  均分 {s['mean_total']:5.1f}  通过率 {s['pass_rate']}%")

    low = sorted([r for r in results if isinstance(r.get("final_total"), (int, float))],
                 key=lambda x: x["final_total"])[:3]
    if low:
        print("\n  🔻 最差 3 条（优先改进）：")
        for r in low:
            print(f"    - [{r['id']}] {r['final_total']} 分 | {r['input'][:28]} | {r['final_reason'][:40]}")


def run_local(limit=None, do_langfuse=False, max_attempts=2):
    """跑一轮本地评测，返回 (report, report_path)。"""
    from agent.multi_agent import MultiAgent  # 延迟导入

    cases = GOLDEN_SET[:limit] if limit else GOLDEN_SET
    print("=" * 60)
    print(f"🤖 评测开始：{len(cases)} 条题目 · 被测=Multi-Agent Router · 记忆=关")
    print("=" * 60)

    agent = MultiAgent(use_memory=False)  # 决策①：关长期记忆，保证可复现
    judge = Judge()

    try:
        results = _run_agent_cases(agent, cases, judge, max_attempts)
    except AbortEval:
        print("\n❌ 评测因环境异常中断，未生成完整报告（部分结果见上）。")
        return None, None

    summary = _summarize(results)
    _print_summary(summary, results)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "target": "MultiAgent(Router+Worker)",
        "judge_model": judge.model,
        "memory": "off",
        "max_attempts": max_attempts,
        "dimensions": DIMENSIONS,
        "summary": summary,
        "results": results,
    }

    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n💾 报告已保存：{path}")

    if do_langfuse:
        _push_to_langfuse(results)
    return report, path


def _push_to_langfuse(results):
    """把本次评测同步到 Langfuse（Dataset + Experiment），在 UI 看板查看。"""
    from agent.langfuse_obs import get_langfuse
    lf = get_langfuse()
    if lf is None:
        print("ℹ️ 未配置 Langfuse，跳过上报（本地报告已保存）")
        return

    ds_name = "ai-agent-golden-set"
    today = datetime.now().strftime("%Y/%m/%d")
    try:
        lf.create_dataset(name=ds_name, description=f"评测金标准数据集（{today}）")
    except Exception:
        pass  # 已存在
    for r in results:
        try:
            lf.create_dataset_item(
                dataset_name=ds_name,
                input=r["input"],
                expected_output=r["expected"],
                metadata={"case_id": r["id"], "category": r["category"], "checks": r["checks"]},
                id=r["id"],
            )
        except Exception:
            pass

    item_results_map = {r["id"]: r for r in results}

    def task(*, item, **kwargs):
        cid = (item.get("metadata") or {}).get("case_id") or item.get("id")
        return item_results_map.get(cid, {}).get("final_answer") or ""

    def judge_eval(*, input, output, expected_output=None, metadata=None, **kwargs):
        cid = (metadata or {}).get("case_id")
        r = item_results_map.get(cid, {})
        return {
            "name": "llm_judge_total",
            "value": r.get("final_total") if r.get("final_total") is not None else 0,
            "comment": r.get("final_reason", ""),
        }

    try:
        data = list(lf.get_dataset(ds_name).items)
        exp = lf.run_experiment(
            name=f"ai-agent-评测-{today}",
            data=data,
            task=task,
            evaluators=[judge_eval],
        )
        print(f"🌐 已上报 Langfuse Experiment：{exp.dataset_run_url or exp.run_name}")
    except Exception as e:
        print(f"⚠️ Langfuse 上报失败（不影响本地报告）：{type(e).__name__}: {e}")


def compare(path_a, path_b):
    """对比两份报告：逐条算分差，指出变好/变差的题。"""
    def load(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    a, b = load(path_a), load(path_b)
    print("=" * 60)
    print(f"📈 对比：\n  A = {os.path.basename(path_a)}  ({a['timestamp']})\n  B = {os.path.basename(path_b)}  ({b['timestamp']})")
    print("=" * 60)
    print(f"  平均总分：{a['summary']['mean_total']} → {b['summary']['mean_total']}")
    print(f"  通过率  ：{a['summary']['pass_rate']}% → {b['summary']['pass_rate']}%")

    amap = {r["id"]: r for r in a["results"]}
    print("\n  逐条变化（B - A）：")
    for r in b["results"]:
        old = amap.get(r["id"])
        if not old or old.get("final_total") is None or r.get("final_total") is None:
            continue
        delta = round(r["final_total"] - old["final_total"], 1)
        if abs(delta) >= 1:
            arrow = "⬆️" if delta > 0 else "⬇️"
            print(f"    {arrow} [{r['id']}] {old['final_total']} → {r['final_total']}  ({delta:+})")


def main():
    ap = argparse.ArgumentParser(description="AI Agent 评测跑批（2026/09/10）")
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 条（快速自检）")
    ap.add_argument("--langfuse", action="store_true", help="额外把评测同步到 Langfuse Experiment")
    ap.add_argument("--max-attempts", type=int, default=2, help="单条最多尝试次数（默认 2）")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"), help="对比两份报告")
    args = ap.parse_args()

    if args.compare:
        compare(*args.compare)
        return
    run_local(limit=args.limit, do_langfuse=args.langfuse, max_attempts=args.max_attempts)


if __name__ == "__main__":
    main()
