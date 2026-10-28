# -*- coding: utf-8 -*-
"""agent/context_budget.py — 请求级上下文预算

三条不变量：
1. 预算约束的是**即将发给模型的 messages**，不是 history 的“事后状态”；
2. 裁剪单位是**完整 turn**，assistant.tool_calls 与对应 tool 必须同生共死；
3. token 估算要保守，并把 tool_calls.arguments 算进去。

这里只做纯函数，不碰网络 / 不依赖 Agent，方便单测。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def estimate_text(text: Any) -> int:
    """保守估算：CJK 1 字≈1 token，非 CJK 4 字符≈1 token，再加结构开销。"""
    s = str(text if text is not None else "")
    if not s:
        return 0
    cjk = len(_CJK.findall(s))
    other = len(s) - cjk
    return max(1, cjk + other // 4 + 1)


def estimate_message(msg: dict) -> int:
    """一条 message 的估算：content + tool_calls.arguments + 角色开销。"""
    n = 4 + estimate_text(msg.get("content", ""))
    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {}) if isinstance(tc, dict) else {}
        n += 4 + estimate_text(fn.get("arguments", ""))
    return n


def estimate_messages(messages: list[dict]) -> int:
    return sum(estimate_message(m) for m in messages)


def group_turns(history: list[dict]) -> tuple[dict | None, list[list[dict]]]:
    """把 history 分成 system + 若干完整 turn。

    一个 turn 从 user 开始，包含其后的 assistant / tool 消息，直到下一个 user。
    这样 tool_calls 与 tool 不会被拆开。
    """
    if not history:
        return None, []
    system = history[0] if history[0].get("role") == "system" else None
    body = history[1:] if system else history[:]
    turns: list[list[dict]] = []
    cur: list[dict] | None = None
    for msg in body:
        if msg.get("role") == "user":
            if cur:
                turns.append(cur)
            cur = [msg]
        else:
            if cur is None:
                cur = [msg]  # 防御：不符合正常结构的历史也先成组
            else:
                cur.append(msg)
    if cur:
        turns.append(cur)
    return system, turns


def check_tool_pairing(messages: list[dict]) -> list[str]:
    """检查 tool_calls 与 tool 的配对；返回问题列表（空=合法）。"""
    issues: list[str] = []
    pending: set[str] = set()
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role == "assistant":
            calls = msg.get("tool_calls", []) or []
            ids = {str(tc.get("id")) for tc in calls if isinstance(tc, dict) and tc.get("id")}
            pending |= ids
        elif role == "tool":
            tid = str(msg.get("tool_call_id") or "")
            if tid not in pending:
                issues.append(f"#{i} tool {tid!r} 没有对应的 assistant.tool_calls")
            pending.discard(tid)
    if pending:
        issues.append(f"assistant.tool_calls 没有对应 tool: {sorted(pending)}")
    return issues


@dataclass
class BudgetResult:
    messages: list[dict]
    tokens: int
    kept_turns: int
    dropped_turns: int
    overflow: bool
    issues: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"tokens={self.tokens} turns={self.kept_turns} "
                f"dropped={self.dropped_turns} overflow={self.overflow} "
                f"issues={self.issues or 'none'}")


def fit_to_budget(history: list[dict], max_tokens: int) -> BudgetResult:
    """构造请求前的裁剪结果。

    - 永远保留 system；
    - 从最旧的完整 turn 开始丢，直到不超预算；
    - 至少保留最新一个 turn（当前问题不能丢）；
    - 如果最新 turn 自己就超预算，返回 overflow=True，由调用方决定摘要/截断，
      而不是拆 tool 配对或丢掉当前用户消息。
    """
    system, turns = group_turns(history)
    kept = list(turns)
    dropped = 0
    while len(kept) > 1:
        body = [m for t in kept for m in t]
        total = estimate_messages(([system] if system else []) + body)
        if total <= max_tokens:
            break
        kept.pop(0)
        dropped += 1
    body = [m for t in kept for m in t]
    messages = ([system] if system else []) + body
    tokens = estimate_messages(messages)
    issues = check_tool_pairing(messages)
    return BudgetResult(messages, tokens, len(kept), dropped,
                        tokens > max_tokens, issues)
