# -*- coding: utf-8 -*-
"""能力 × 编排 v2 · 正测 runner（2026-10-19）

只做一件事：跑 2×2（强/弱 × solo/EC）的数值题，确定性判分，逐行落盘。

用法（先 smoke，一次一格）：
    .venv/bin/python docs/experiments/capability_x_positive.py \
        --cell strong-solo --n 1 --task T1
    .venv/bin/python docs/experiments/capability_x_positive.py \
        --cell strong-ec   --n 1 --task T1
    .venv/bin/python docs/experiments/capability_x_positive.py \
        --cell weak-solo   --n 1 --task T1
    .venv/bin/python docs/experiments/capability_x_positive.py \
        --cell weak-ec     --n 1 --task T1

设计：docs/02-编排章/能力与编排正测设计.md
不修改 agent/ 下任何代码；EC 是数值版（不复用文案专用的 evaluator_critic.py）。
"""
import argparse
import contextlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

import logging

logging.disable(logging.CRITICAL)

from openai import OpenAI

from agent.core import Agent
from agent.json_mode import parse_json_strict

STRONG_MODEL = os.getenv("STRONG_MODEL", "deepseek-flash")
WEAK_MODEL = os.getenv("WEAK_MODEL", "qwen-flash")

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "")

if not DEEPSEEK_KEY or not DASHSCOPE_KEY:
    raise SystemExit("缺少 DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY（见 .env）")

from _gap_demo import TASKS, last_num  # 单一题面来源，避免两处漂移

DEEPSEEK = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
DASHSCOPE = OpenAI(
    api_key=DASHSCOPE_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

CELLS = {
    "strong-solo": {"model": STRONG_MODEL, "client": DEEPSEEK, "mode": "solo"},
    "strong-ec": {"model": STRONG_MODEL, "client": DEEPSEEK, "mode": "ec"},
    "weak-solo": {"model": WEAK_MODEL, "client": DASHSCOPE, "mode": "solo"},
    "weak-ec": {"model": WEAK_MODEL, "client": DASHSCOPE, "mode": "ec"},
}

GENERATOR_SYSTEM = "你是严谨的系统工程师。只输出要求的那个数字，不要解释。"

CRITIC_SYSTEM = (
    "你是独立的数值复核员。你的唯一任务是独立重算题目，并核对候选答案。"
    "不要相信候选答案；不要评价文风；不要解释。只输出一个 JSON 对象。"
    "第一步必须逐字复述候选答案，不得改写、四舍五入或替换成你算出的数。"
)

CRITIC_INSTRUCTION = (
    "先逐字复述候选答案，再独立重算。只输出 JSON："
    '{"candidate_seen": "候选答案原文", "consistent": true/false, '
    '"issues": ["..."], "recomputed": 数字}\n'
    "candidate_seen 必须与候选答案原文完全一致（包括负号、小数点、空格）；"
    "一致时 consistent=true、issues=[]；不一致时 consistent=false，"
    "issues 写清哪一步/哪个数不对；recomputed 是你算出的数。"
)

TASK_MAP = {name: (text, expect, tol) for name, text, expect, tol in TASKS}


def _agent(cfg):
    return Agent(
        system_prompt=GENERATOR_SYSTEM,
        model=cfg["model"],
        client=cfg["client"],
    )


def _usage_of(agent_obj):
    u = agent_obj.usage
    return {
        "prompt_tokens": u.get("prompt_tokens", 0),
        "completion_tokens": u.get("completion_tokens", 0),
        "total_tokens": u.get("total_tokens", 0),
    }


def _run_generator(cfg, prompt, max_steps=2):
    a = _agent(cfg)
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(prompt, max_steps=max_steps) or ""
    return out, _usage_of(a), round((time.time() - t0) * 1000, 1)


def _call_critic(cfg, task, candidate, correction=""):
    client = cfg["client"]
    t0 = time.time()
    user_content = (
        f"题目：{task}\n\n"
        f"候选答案原文（逐字复述，不要改写）：\n<<<\n{candidate}\n>>>\n\n"
        f"{CRITIC_INSTRUCTION}"
    )
    if correction:
        user_content += (
            f"\n\n【上一次的问题】{correction}\n"
            "请重新逐字复述候选答案原文，再复核。"
        )
    messages = [
        {"role": "system", "content": CRITIC_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    kwargs = dict(model=cfg["model"], messages=messages, temperature=0)
    try:
        resp = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception as e:
        # 少数兼容端点不支持 response_format：降级重试一次
        if "response_format" in str(e):
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    content = resp.choices[0].message.content or ""
    data = parse_json_strict(content)
    u = resp.usage
    usage = {
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
        "total_tokens": getattr(u, "total_tokens", 0) or 0,
    }
    return data, usage, content, round((time.time() - t0) * 1000, 1)


def _norm_answer(value):
    """比较用归一化：去空白、去包裹引号。不改数字本身。"""
    s = " ".join(str(value or "").split()).strip()
    return s.strip('"\'“”')


def _same_answer(seen, actual):
    """候选答案复述是否保真。数值等价也算一致（9 vs 9.0）。"""
    a, b = _norm_answer(seen), _norm_answer(actual)
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except Exception:
        return False


def _critic_with_fidelity(cfg, task, candidate):
    """调用批判者，并校验它是否逐字复述了候选答案。

    第一次复述错了 -> 带着"你复述成了 X，原文是 Y"重试一次。
    第二次还错 -> 标记 misread=True，调用方**不得**据此重做。
    """
    out = {
        "data": {},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "wall": 0.0,
        "attempts": 0,
        "first_misread": False,
        "misread": False,
        "seen": "",
        "contents": [],
    }
    correction = ""
    for attempt in range(2):
        out["attempts"] += 1
        data, usage, content, wall = _call_critic(cfg, task, candidate, correction)
        for k in out["usage"]:
            out["usage"][k] += usage[k]
        out["wall"] += wall
        out["contents"].append(content)
        out["data"] = data
        if data.get("_parse_error"):
            out["misread"] = True  # 无法校验复述，按不可信处理
            return out
        seen = data.get("candidate_seen", "")
        out["seen"] = seen
        if _same_answer(seen, candidate):
            out["misread"] = False
            return out
        if attempt == 0:
            out["first_misread"] = True
            correction = f"你上次把候选答案复述成了 {seen!r}，但原文是 {candidate!r}。"
        else:
            out["misread"] = True
            return out
    out["misread"] = True
    return out


def run_solo(cfg, task):
    raw, usage, wall_ms = _run_generator(cfg, task)
    return raw, {
        "rounds": 1,
        **usage,
        "wall_ms": wall_ms,
        "critic_consistent": None,
        "critic_issues": [],
        "critic_recomputed": None,
        "critic_flag_mismatch": False,
        "critic_parse_error": False,
        "critic_error": "",
        "critic_attempts": 0,
        "critic_misread": False,
        "critic_first_misread": False,
        "candidate_seen": None,
        "critic_raw": "",
        "redo_used": False,
        "redo_error": "",
    }


def run_ec(cfg, task, max_rounds=2):
    raw1, usage1, wall1 = _run_generator(cfg, task)
    meta = {
        "rounds": 1,
        "prompt_tokens": usage1["prompt_tokens"],
        "completion_tokens": usage1["completion_tokens"],
        "total_tokens": usage1["total_tokens"],
        "wall_ms": wall1,
        "critic_consistent": None,
        "critic_issues": [],
        "critic_recomputed": None,
        "critic_flag_mismatch": False,
        "critic_parse_error": False,
        "critic_error": "",
        "critic_attempts": 0,
        "critic_misread": False,
        "critic_first_misread": False,
        "candidate_seen": None,
        "critic_raw": "",
        "redo_used": False,
        "redo_error": "",
    }
    if max_rounds < 2:
        return raw1, meta

    try:
        c = _critic_with_fidelity(cfg, task, raw1)
    except Exception as e:
        meta["critic_error"] = f"{type(e).__name__}: {e}"
        return raw1, meta

    cusage = c["usage"]
    meta["prompt_tokens"] += cusage["prompt_tokens"]
    meta["completion_tokens"] += cusage["completion_tokens"]
    meta["total_tokens"] += cusage["total_tokens"]
    meta["wall_ms"] = round(meta["wall_ms"] + c["wall"], 1)
    meta["critic_attempts"] = c["attempts"]
    meta["critic_misread"] = c["misread"]
    meta["critic_first_misread"] = c["first_misread"]
    meta["candidate_seen"] = c["seen"]
    meta["critic_raw"] = (c["contents"][-1] if c["contents"] else "")[:2000]

    data = c["data"]
    if data.get("_parse_error"):
        meta["critic_parse_error"] = True
        return raw1, meta
    consistent = data.get("consistent") is True
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    meta["critic_consistent"] = consistent
    meta["critic_issues"] = issues
    recomputed = data.get("recomputed")
    meta["critic_recomputed"] = recomputed
    if c["misread"]:
        # 复述不保真：批判意见不可信，不据此重做
        return raw1, meta

    # 代码级兜底：口头说 consistent，但自己算出的数跟候选不一致 -> 强制重做
    if recomputed is not None and not _same_answer(recomputed, raw1):
        meta["critic_flag_mismatch"] = True
        if not issues:
            issues = [f"复核者重算得到 {recomputed}，与候选答案 {raw1} 不一致；请重新核算。"]
            meta["critic_issues"] = issues

    need_redo = (not consistent) or bool(issues) or meta["critic_flag_mismatch"]
    if not need_redo:
        return raw1, meta

    # 只把 issues 回给生成者，不直接给复核者算出的数字（避免"抄答案"）
    critique = "；".join(str(x) for x in issues)[:1200] or "复核认为答案不一致，请重新核算。"
    redo_prompt = (
        f"{task}\n\n【独立复核意见】{critique}\n\n"
        "请根据复核意见重新计算，只输出一个数。"
    )
    try:
        raw2, usage2, wall2 = _run_generator(cfg, redo_prompt)
    except Exception as e:
        meta["redo_error"] = f"{type(e).__name__}: {e}"
        return raw1, meta

    meta["rounds"] = 2
    meta["redo_used"] = True
    meta["prompt_tokens"] += usage2["prompt_tokens"]
    meta["completion_tokens"] += usage2["completion_tokens"]
    meta["total_tokens"] += usage2["total_tokens"]
    meta["wall_ms"] = round(meta["wall_ms"] + wall2, 1)
    return raw2, meta


def score(raw, expect, tol):
    if not raw or not str(raw).strip():
        return "ERR", None, "empty"
    got = last_num(raw)
    if got is None:
        return "ERR", None, "no_number"
    if abs(got - expect) <= tol:
        return "OK", got, ""
    return "WRONG", got, f"got={got}"


def resolve_tasks(prefix):
    matches = [t for t in TASKS if t[0].lower().startswith(prefix.lower())]
    if not matches:
        raise SystemExit(f"未知题号: {prefix}。可选: {[t[0] for t in TASKS]}")
    return matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True, choices=sorted(CELLS))
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--task", default="T1", help="题号前缀，如 T1 / T6 / all")
    ap.add_argument(
        "--out",
        default=os.path.join(ROOT, "tmp-artifacts", "capability_x_positive.jsonl"),
    )
    ap.add_argument("--max-rounds", type=int, default=2)
    args = ap.parse_args()

    if args.task.lower() == "all":
        tasks = TASKS
    else:
        tasks = resolve_tasks(args.task)

    if not DEEPSEEK_KEY or not DASHSCOPE_KEY:
        raise SystemExit("缺少 DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY（见 .env）")

    cfg = CELLS[args.cell]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    print(f"cell={args.cell} model={cfg['model']} mode={cfg['mode']} n={args.n} tasks={[t[0] for t in tasks]}")

    counts = {"OK": 0, "WRONG": 0, "ERR": 0}
    total_tokens = 0
    wall_total = 0.0
    for tname, task, expect, tol in tasks:
        for i in range(args.n):
            run_id = f"{args.cell}-{tname}-{i + 1}-{int(time.time() * 1000)}"
            started = datetime.now(timezone.utc).isoformat()
            try:
                if cfg["mode"] == "solo":
                    raw, meta = run_solo(cfg, task)
                else:
                    raw, meta = run_ec(cfg, task, max_rounds=args.max_rounds)
                status, got, note = score(raw, expect, tol)
            except Exception as e:
                raw, got, note = "", None, f"{type(e).__name__}: {e}"
                status = "ERR"
                meta = {"rounds": 0, "prompt_tokens": 0, "completion_tokens": 0,
                        "total_tokens": 0, "wall_ms": 0, "critic_error": note}

            rec = {
                "run_id": run_id,
                "task": tname,
                "cell": args.cell,
                "model": cfg["model"],
                "mode": cfg["mode"],
                "expect": expect,
                "parsed_value": got,
                "status": status,
                "note": note,
                "raw_answer": raw,
                "started_at": started,
                **meta,
            }
            with open(args.out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

            counts[status] += 1
            total_tokens += meta.get("total_tokens", 0) or 0
            wall_total += meta.get("wall_ms", 0) or 0
            print(
                f"  [{tname} #{i + 1}] {status} got={got} "
                f"rounds={meta.get('rounds')} tokens={meta.get('total_tokens')} "
                f"wall={meta.get('wall_ms')}ms raw={str(raw)[:80]!r}"
            )
            if meta.get("critic_error"):
                print(f"    critic_error: {meta['critic_error']}")
            if meta.get("redo_error"):
                print(f"    redo_error: {meta['redo_error']}")

    print(f"\nsummary {args.cell}: {counts} total_tokens={total_tokens} wall={round(wall_total, 1)}ms")
    print(f"raw -> {args.out}")


if __name__ == "__main__":
    main()
