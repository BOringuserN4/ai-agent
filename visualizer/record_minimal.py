#!/usr/bin/env python3
"""跑一次真实的 minimal.py 循环，并把过程写成事件 JSONL。

用法：
    .venv/bin/python visualizer/record_minimal.py "请用工具计算 123 * 456"
    .venv/bin/python visualizer/record_minimal.py "..." --out visualizer/trace.jsonl

注意：这会真实调用一次 DeepSeek API；不会把 key 写进 trace。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from openai import OpenAI

from agent.events import EventBus, JsonlSink, new_run_id
from minimal import SYSTEM_PROMPT, TOOLS_SPEC, TOOL_FUNCTIONS

load_dotenv(str(ROOT / ".env"))


def tool_names() -> list[str]:
    return [t["function"]["name"] for t in TOOLS_SPEC]


def message_dict(m) -> dict:
    """把 OpenAI message 或本地 tool message 变成可 JSON 的 dict。"""
    if isinstance(m, dict):
        d = {"role": m.get("role", "tool"), "content": m.get("content", "")}
        if m.get("tool_call_id"):
            d["tool_call_id"] = m["tool_call_id"]
        return d
    d = {"role": getattr(m, "role", "assistant"), "content": getattr(m, "content", None) or ""}
    tcs = getattr(m, "tool_calls", None)
    if tcs:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in tcs
        ]
    return d


def estimate_messages(messages: list[dict]) -> int:
    # 粗略：4 字符 / token + 每条消息结构开销；只用于动画展示
    total = 0
    for m in messages:
        total += 8
        total += max(1, len(str(m.get("content", ""))) // 4)
        for tc in m.get("tool_calls", []) or []:
            total += max(1, len(str(tc.get("arguments", ""))) // 4)
    return total


def usage_dict(resp) -> dict:
    u = getattr(resp, "usage", None)
    return {
        "prompt_tokens": int(getattr(u, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(u, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(u, "total_tokens", 0) or 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="用户问题")
    ap.add_argument("--out", default=str(ROOT / "visualizer" / "trace.jsonl"))
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--max-steps", type=int, default=6)
    args = ap.parse_args()

    key = os.getenv("DEEPSEEK_API_KEY", "")
    if len(key) < 10:
        raise SystemExit("❌ 请先在 .env 配置 DEEPSEEK_API_KEY")

    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    run_id = new_run_id()
    sink = JsonlSink(args.out)
    bus = EventBus(run_id=run_id, sinks=[sink])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": args.prompt},
    ]
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    t_run = time.perf_counter()
    llm_calls = 0
    tool_calls = 0
    answer = ""

    def emit_context(reason: str, step: int) -> None:
        trace_messages = [message_dict(m) for m in messages]
        bus.emit(
            "context_built",
            {
                "reason": reason,
                "messages": trace_messages,
                "est_tokens": estimate_messages(trace_messages),
            },
            step=step,
        )

    bus.emit(
        "run_start",
        {
            "model": args.model,
            "tools": tool_names(),
            "system_prompt": SYSTEM_PROMPT,
            "user_input": args.prompt,
        },
        step=0,
    )
    emit_context("initial", 0)

    for step in range(1, args.max_steps + 1):
        bus.emit(
            "llm_request",
            {
                "model": args.model,
                "messages": [message_dict(m) for m in messages],
                "tools": tool_names(),
                "temperature": 0.3,
            },
            step=step,
        )

        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=args.model,
            messages=messages,
            tools=TOOLS_SPEC,
            temperature=0.3,
        )
        duration_ms = round((time.perf_counter() - t0) * 1000)
        llm_calls += 1
        msg = resp.choices[0].message
        usage = usage_dict(resp)
        for k in total:
            total[k] += usage[k]

        bus.emit(
            "llm_response",
            {
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in (msg.tool_calls or [])
                ],
                "finish_reason": resp.choices[0].finish_reason,
                "duration_ms": duration_ms,
            },
            step=step,
            usage=usage,
        )

        messages.append(msg)

        if not msg.tool_calls:
            answer = msg.content or ""
            break

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments or "{}")
            except Exception:
                fn_args = {}
            bus.emit(
                "tool_call",
                {"name": name, "args": fn_args, "call_id": tc.id},
                step=step,
            )

            t_tool = time.perf_counter()
            fn = TOOL_FUNCTIONS.get(name)
            try:
                result = fn(**fn_args) if fn else f"❌ 未知工具: {name}"
                ok = not str(result).startswith("❌")
            except Exception as e:
                result = f"❌ 工具异常: {e}"
                ok = False
            tool_ms = round((time.perf_counter() - t_tool) * 1000)
            tool_calls += 1

            bus.emit(
                "tool_result",
                {
                    "name": name,
                    "result": str(result),
                    "ok": ok,
                    "duration_ms": tool_ms,
                },
                step=step,
            )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
            )

        emit_context("after_tool", step)

    else:
        answer = "⚠️ 达到最大步数仍未收敛"

    bus.emit(
        "run_end",
        {
            "answer": answer,
            "steps": step,
            "llm_calls": llm_calls,
            "tool_calls": tool_calls,
            "total_usage": total,
            "wall_ms": round((time.perf_counter() - t_run) * 1000),
        },
        step=step,
    )

    print(f"trace: {args.out}")
    print(f"run_id: {run_id}")
    print(f"events: {bus.seq} | llm: {llm_calls} | tool: {tool_calls} | tokens: {total['total_tokens']}")
    print(f"answer: {answer[:200]}")


if __name__ == "__main__":
    main()
