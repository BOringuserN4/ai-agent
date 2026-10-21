#!/usr/bin/env python3
"""录一条“开发统计数据小工具”的真实 trace。

场景：
  用户给一个 sales.csv，要求写 stats_tool.py，按 category 统计
  count / sum / avg，输出 JSON；先写文件，再运行验证。

工具：write_file / read_file / run_python（都限制在临时工作目录）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from openai import OpenAI

from agent.events import EventBus, JsonlSink, new_run_id
from agent.memory import MemoryStore, format_context

load_dotenv(str(ROOT / ".env"))

SYSTEM = """你是一个会写代码的助手。
工作目录：{workspace}
目录里有 sales.csv（列：category,value）。
要求：写一个 Python 脚本 stats_tool.py，读取 sales.csv，
按 category 统计 count / sum / avg，按用户偏好输出。
必须先用 write_file 写文件，再用 run_python 运行验证；
不要心算或编造输出。"""


def session() -> tuple[Path, OpenAI]:
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if len(key) < 10:
        raise SystemExit("❌ 请先在 .env 配置 DEEPSEEK_API_KEY")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


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


def estimate_messages(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += 8 + max(1, len(str(m.get("content", ""))) // 4)
        for tc in m.get("tool_calls", []) or []:
            total += max(1, len(str(tc.get("arguments", ""))) // 4)
    return total


def usage(resp) -> dict:
    u = getattr(resp, "usage", None)
    return {
        "prompt_tokens": int(getattr(u, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(u, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(u, "total_tokens", 0) or 0),
    }


def make_tools(workspace: Path):
    def safe(path: str) -> Path:
        p = (workspace / path).resolve()
        if workspace.resolve() not in p.parents and p != workspace.resolve():
            raise ValueError("path escapes workspace")
        return p

    def write_file(path: str, content: str) -> str:
        p = safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {p.name} ({len(content)} chars)"

    def read_file(path: str) -> str:
        p = safe(path)
        text = p.read_text(encoding="utf-8")
        return text[:4000]

    def run_python(path: str) -> str:
        p = safe(path)
        try:
            cp = subprocess.run(
                [sys.executable, str(p)],
                cwd=workspace, capture_output=True, text=True, timeout=20,
            )
            return json.dumps(
                {"exit_code": cp.returncode, "stdout": cp.stdout[-4000:], "stderr": cp.stderr[-2000:]},
                ensure_ascii=False,
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"exit_code": -1, "stdout": "", "stderr": "timeout"}, ensure_ascii=False)

    return {
        "write_file": write_file,
        "read_file": read_file,
        "run_python": run_python,
    }


SPEC = [
    {"type": "function", "function": {
        "name": "write_file",
        "description": "在工作目录写一个文件。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取工作目录里的文件。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "run_python",
        "description": "用 Python 运行工作目录里的脚本，返回 exit_code / stdout / stderr。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
        }, "required": ["path"]},
    }},
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "visualizer" / "trace_dev.jsonl"))
    ap.add_argument("--max-steps", type=int, default=3)
    args = ap.parse_args()

    client = session()
    workspace = Path(tempfile.mkdtemp(prefix="agent-dev-"))
    (workspace / "sales.csv").write_text(
        "category,value\nA,10\nB,20\nA,30\nB,40\nC,50\n", encoding="utf-8"
    )
    tools = make_tools(workspace)

    bus = EventBus(run_id=new_run_id(), sinks=[JsonlSink(args.out)])
    task = "帮我写一个统计数据的小工具：读取 sales.csv，按 category 统计 count/sum/avg，按我的偏好输出；先写文件，再运行验证。"

    # 记忆：用户偏好 JSON（独立临时库，不碰真实记忆）
    store = MemoryStore(chroma_dir=str(Path(tempfile.gettempdir()) / "ai-agent-viz-dev-chroma"))
    store.clear()
    store.add(
        "用户偏好：统计结果用 JSON 输出。",
        meta={"type": "seed", "tags": ["preference", "format"]},
        embed_text="用户偏好：统计结果用 JSON 输出。可能被问：按我的偏好输出？结果用什么格式？",
    )
    base_system = SYSTEM.format(workspace=workspace)
    messages = [{"role": "system", "content": base_system}, {"role": "user", "content": task}]
    bus.emit("run_start", {
        "model": "deepseek-flash",
        "tools": ["write_file", "read_file", "run_python"],
        "modules": ["llm", "memory", "tools", "extractor", "guard", "tracer", "eval", "mcp"],
        "task": task,
        "workspace": str(workspace),
    }, step=0)

    hits = store.search(task)
    bus.emit("memory_search", {"query": task, "hits": hits, "top_k": store.top_k}, step=0)
    memory_context = format_context(hits) if hits else ""

    bus.emit("context_built", {
        "reason": "initial",
        "messages": [msg_dict(m) for m in messages],
        "est_tokens": estimate_messages([msg_dict(m) for m in messages]),
    }, step=0)

    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    tool_count = 0
    answer = ""
    t_run = time.perf_counter()
    step = 0

    for step in range(1, args.max_steps + 1):
        remaining = args.max_steps - step
        system = base_system
        if memory_context:
            system += "\n\n" + memory_context
        if remaining <= 2:
            system += f"\n\n【重要】剩余轮次不多（约 {remaining} 轮）。请尽快基于已有结果给出结论。"
        call_messages = [{"role": "system", "content": system}] + messages[1:]

        bus.emit("llm_request", {
            "model": "deepseek-flash",
            "messages": [msg_dict(m) for m in call_messages],
            "tools": [s["function"]["name"] for s in SPEC],
            "temperature": 0.2,
        }, step=step)
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model="deepseek-flash", messages=call_messages, tools=SPEC, temperature=0.2,
        )
        elapsed = round((time.perf_counter() - t0) * 1000)
        u = usage(resp)
        for k in total:
            total[k] += u[k]
        msg = resp.choices[0].message
        tcs = [
            {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
            for tc in (msg.tool_calls or [])
        ]
        bus.emit("llm_response", {
            "content": msg.content or "",
            "tool_calls": tcs,
            "finish_reason": resp.choices[0].finish_reason,
            "duration_ms": elapsed,
        }, step=step, usage=u)

        messages.append(msg)
        if not msg.tool_calls:
            answer = msg.content or ""
            break

        if tcs and remaining <= 2:
            bus.emit("budget_warning", {"remaining": remaining, "max_steps": args.max_steps}, step=step)

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments or "{}")
            except Exception:
                fn_args = {}
            bus.emit("tool_call", {"name": name, "args": fn_args}, step=step)
            t_tool = time.perf_counter()
            try:
                result = tools[name](**fn_args) if name in tools else f"❌ 未知工具: {name}"
                ok = not str(result).startswith("❌")
            except Exception as e:
                result = f"❌ 工具异常: {e}"
                ok = False
            tool_count += 1
            bus.emit("tool_result", {
                "name": name, "result": str(result), "ok": ok,
                "duration_ms": round((time.perf_counter() - t_tool) * 1000),
            }, step=step)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

        # 工具结果回填后的上下文
        bus.emit("context_built", {
            "reason": "after_tool",
            "messages": [msg_dict(m) for m in messages],
            "est_tokens": estimate_messages([msg_dict(m) for m in messages]),
        }, step=step)

    bus.emit("run_end", {
        "answer": answer,
        "steps": step,
        "llm_calls": step,
        "tool_calls": tool_count,
        "total_usage": total,
        "wall_ms": round((time.perf_counter() - t_run) * 1000),
        "workspace": str(workspace),
    }, step=step)

    print(f"trace: {args.out}")
    print(f"events: {bus.seq} | steps: {step} | tools: {tool_count} | tokens: {total['total_tokens']}")
    print(f"workspace: {workspace}")
    print(f"answer: {answer[:300]}")


if __name__ == "__main__":
    main()
