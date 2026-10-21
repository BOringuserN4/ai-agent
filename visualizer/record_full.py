#!/usr/bin/env python3
"""录一条更复杂的 trace：记忆 + 两个工具 + 预算 + Extractor。

流程：
  1. 用独立 Chroma 目录种两条记忆；
  2. 单 Agent 跑任务：记忆检索 → calculator + current_time → 最终回答；
  3. 回答后 extractor 沉淀一条记忆；
  4. 全程写 JSONL，供 visualizer 回放。

用法：
    .venv/bin/python visualizer/record_full.py
    .venv/bin/python visualizer/record_full.py --out visualizer/trace_full.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from openai import OpenAI

from agent.core import Agent
from agent.events import EventBus, JsonlSink, new_run_id
from agent.memory import MemoryStore

load_dotenv(str(ROOT / ".env"))


def msg_dict(m) -> dict:
    if isinstance(m, dict):
        d = {"role": m.get("role", "tool"), "content": m.get("content", "")}
        if m.get("tool_call_id"):
            d["tool_call_id"] = m["tool_call_id"]
        return d
    d = {"role": getattr(m, "role", "assistant"), "content": getattr(m, "content", None) or ""}
    tcs = getattr(m, "tool_calls", None)
    if tcs:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in tcs
        ]
    return d


def estimate_messages(messages) -> int:
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


class ChatProxy:
    """代理 OpenAI client：在每次请求前后发事件。"""

    def __init__(self, real, bus: EventBus, max_steps: int):
        self.real = real
        self.bus = bus
        self.max_steps = max_steps
        self.calls = 0
        self.last_step = 0
        self.tool_calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls += 1
        step = self.calls
        self.last_step = step
        messages = [msg_dict(m) for m in kwargs.get("messages", [])]
        self.bus.emit(
            "context_built",
            {
                "reason": "initial" if step == 1 else "after_tool",
                "messages": messages,
                "est_tokens": estimate_messages(messages),
            },
            step=step,
        )
        self.bus.emit(
            "llm_request",
            {
                "model": kwargs.get("model", ""),
                "messages": messages,
                "tools": [t["function"]["name"] for t in kwargs.get("tools", [])],
                "temperature": kwargs.get("temperature"),
            },
            step=step,
        )

        t0 = time.perf_counter()
        resp = self.real.chat.completions.create(**kwargs)
        duration_ms = round((time.perf_counter() - t0) * 1000)
        msg = resp.choices[0].message
        usage = usage_dict(resp)
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (msg.tool_calls or [])
        ]
        self.bus.emit(
            "llm_response",
            {
                "content": msg.content or "",
                "tool_calls": tool_calls,
                "finish_reason": resp.choices[0].finish_reason,
                "duration_ms": duration_ms,
            },
            step=step,
            usage=usage,
        )
        if tool_calls and step == 1 and self.max_steps <= 2:
            self.bus.emit(
                "budget_warning",
                {"remaining": self.max_steps - step, "max_steps": self.max_steps},
                step=step,
            )
        return resp


class MemoryProxy:
    """代理 MemoryStore：检索/写入时发事件。"""

    def __init__(self, store: MemoryStore, bus: EventBus, chat: ChatProxy):
        self.store = store
        self.bus = bus
        self.chat = chat
        self.written: set[str] = set()

    def search(self, query, *args, **kwargs):
        t0 = time.perf_counter()
        hits = self.store.search(query, *args, **kwargs)
        self.bus.emit(
            "memory_search",
            {
                "query": query,
                "hits": hits,
                "top_k": kwargs.get("top_k") or self.store.top_k,
                "duration_ms": round((time.perf_counter() - t0) * 1000),
            },
            step=0,
        )
        return hits

    def add(self, text, meta=None, embed_text=None):
        self.store.add(text, meta=meta, embed_text=embed_text)
        if text in self.written:
            return
        self.written.add(text)
        self.bus.emit(
            "memory_write",
            {
                "keep": True,
                "text": text,
                "tags": (meta or {}).get("tags", []),
                "meta": meta or {},
            },
            step=self.chat.last_step or 0,
        )

    def __getattr__(self, name):
        return getattr(self.store, name)


def wrap_tool(name: str, fn, bus: EventBus, chat: ChatProxy):
    def wrapped(**kwargs):
        step = chat.last_step or 1
        chat.tool_calls += 1
        bus.emit("tool_call", {"name": name, "args": kwargs}, step=step)
        t0 = time.perf_counter()
        try:
            result = fn(**kwargs)
            ok = not str(result).startswith("❌")
        except Exception as e:
            result = f"❌ 工具异常: {e}"
            ok = False
        bus.emit(
            "tool_result",
            {
                "name": name,
                "result": str(result),
                "ok": ok,
                "duration_ms": round((time.perf_counter() - t0) * 1000),
            },
            step=step,
        )
        return result

    return wrapped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "visualizer" / "trace_full.jsonl"))
    ap.add_argument("--max-steps", type=int, default=2)
    args = ap.parse_args()

    key = os.getenv("DEEPSEEK_API_KEY", "")
    if len(key) < 10:
        raise SystemExit("❌ 请先在 .env 配置 DEEPSEEK_API_KEY")

    task = "我的职业是什么？请先算 123 * 456，再查上海现在的时间，然后结合我的职业，用一句话总结。"
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    run_id = new_run_id()
    bus = EventBus(run_id=run_id, sinks=[JsonlSink(args.out)])

    # 1) 独立记忆库 + 种两条事实（不碰真实记忆）
    chroma_dir = Path(tempfile.gettempdir()) / "ai-agent-viz-chroma"
    store = MemoryStore(chroma_dir=str(chroma_dir))
    store.clear()
    store.add(
        "用户叫小王，是一名测试开发工程师。",
        meta={"type": "seed", "tags": ["personal_info", "job"]},
        embed_text="用户叫小王，是一名测试开发工程师。可能被问：我的职业是什么？我做什么工作？我是谁？结合我的职业。",
    )
    store.add(
        "用户在做测试开发，最近在学习 Agent。",
        meta={"type": "seed", "tags": ["job", "interest"]},
        embed_text="用户在做测试开发，最近在学习 Agent。可能被问：我的职业是什么？我做什么工作？我的兴趣是什么？",
    )

    bus.emit(
        "run_start",
        {
            "model": os.getenv("LLM_MODEL", "deepseek-flash"),
            "tools": ["calculator", "current_time"],
            "modules": ["llm", "memory", "tools", "extractor", "guard", "tracer", "eval", "mcp"],
            "task": task,
        },
        step=0,
    )

    # 3) Agent：记忆 + 两个工具 + 预算
    chat = ChatProxy(client, bus, args.max_steps)
    mem = MemoryProxy(store, bus, chat)
    agent = Agent(
        system_prompt="你是一个助手。需要计算或查时间时必须调用工具，不要心算或编造。回答时结合已知用户信息。",
        tools=("calculator", "current_time"),
        memory=mem,
        client=chat,
    )
    for name, fn in list(agent.tool_registry.items()):
        agent.tool_registry[name] = wrap_tool(name, fn, bus, chat)

    t_run = time.perf_counter()
    answer = agent.run(task, max_steps=args.max_steps, max_tokens=6000)

    # 4) 等后台 extractor 写完记忆（它是 daemon thread）
    time.sleep(8)

    bus.emit(
        "run_end",
        {
            "answer": answer,
            "steps": chat.calls,
            "llm_calls": chat.calls,
            "tool_calls": chat.tool_calls,
            "total_usage": dict(agent.usage),
            "wall_ms": round((time.perf_counter() - t_run) * 1000),
        },
        step=chat.calls,
    )

    print(f"trace: {args.out}")
    print(f"run_id: {run_id}")
    print(f"events: {bus.seq}")
    print(f"answer: {answer[:200]}")


if __name__ == "__main__":
    main()
