# -*- coding: utf-8 -*-
"""上下文预算回归测试（不调 API）。"""
import unittest
from types import SimpleNamespace

from agent.context_budget import (
    BudgetResult, check_tool_pairing, estimate_messages, estimate_text,
    fit_to_budget,
)
from agent.core import Agent


class StubCompletions:
    def __init__(self):
        self.seen = None

    def create(self, **kwargs):
        self.seen = kwargs.get("messages", [])
        msg = SimpleNamespace(content="done", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class StubClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=StubCompletions())


def long_history():
    h = [{"role": "system", "content": "你是助手。"}]
    for i in range(12):
        h += [
            {"role": "user", "content": f"第{i}轮：" + "历史" * 80},
            {"role": "assistant", "content": f"回答{i}：" + "内容" * 80},
        ]
    h.append({"role": "user", "content": "现在的新问题"})
    return h


def tool_history():
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u" * 100},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "calculator", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": "r" * 100},
        {"role": "assistant", "content": "a" * 100},
    ]


class ToolStubCompletions:
    def __init__(self):
        self.seen = []
        self.calls = 0

    def create(self, **kwargs):
        self.seen.append(kwargs.get("messages", []))
        self.calls += 1
        if self.calls == 1:
            tc = SimpleNamespace(
                id="c1",
                function=SimpleNamespace(name="calculator", arguments='{"expression":"1+1"}'),
            )
            msg = SimpleNamespace(content="", tool_calls=[tc])
        else:
            msg = SimpleNamespace(content="2", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class ToolStubClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=ToolStubCompletions())


class ContextBudgetTest(unittest.TestCase):
    def test_long_history_fits_and_keeps_current(self):
        r = fit_to_budget(long_history(), max_tokens=200)
        self.assertIsInstance(r, BudgetResult)
        self.assertLessEqual(r.tokens, 200)
        self.assertTrue(any("现在的新问题" in str(m.get("content", "")) for m in r.messages))
        self.assertFalse(any("第0轮" in str(m.get("content", "")) for m in r.messages))
        self.assertGreater(r.dropped_turns, 0)

    def test_tool_turn_is_kept_whole(self):
        r = fit_to_budget(tool_history(), max_tokens=101)
        self.assertEqual(r.issues, [])
        self.assertTrue(any(m.get("role") == "tool" for m in r.messages))
        self.assertTrue(any(m.get("tool_calls") for m in r.messages))
        # 最新 turn 自己超预算：允许 overflow，但不能拆配对
        self.assertTrue(r.overflow)

    def test_check_tool_pairing_detects_orphan(self):
        orphan = [
            {"role": "system", "content": "s"},
            {"role": "tool", "tool_call_id": "c1", "content": "r"},
            {"role": "assistant", "content": "a"},
        ]
        self.assertTrue(check_tool_pairing(orphan))

    def test_estimator_is_conservative_for_cjk(self):
        text = "上下文预算不是历史长度，而是请求里放什么。"
        self.assertGreater(estimate_text(text), max(1, len(text) // 2))

    def test_agent_request_obeys_budget(self):
        stub = StubClient()
        agent = Agent(client=stub, tools=("calculator",))
        agent.history = long_history()[:-1]  # 去掉预先放的当前问题；run 会追加
        agent.run("现在的新问题", max_steps=1, max_tokens=200)
        seen = stub.chat.completions.seen
        self.assertIsNotNone(seen)
        self.assertLessEqual(estimate_messages(seen), 200)
        self.assertTrue(any("现在的新问题" in str(m.get("content", "")) for m in seen))
        self.assertFalse(any("第0轮" in str(m.get("content", "")) for m in seen))

    def test_trim_history_returns_result(self):
        agent = Agent(client=StubClient(), tools=("calculator",))
        agent.history = tool_history()
        r = agent.trim_history(max_tokens=101)
        self.assertIsInstance(r, BudgetResult)
        self.assertEqual(r.issues, [])
        self.assertTrue(r.overflow)
        self.assertTrue(any(m.get("role") == "user" for m in agent.history))

    def test_agent_tool_turn_stays_paired(self):
        stub = ToolStubClient()
        agent = Agent(client=stub, tools=("calculator",))
        agent.run("1+1", max_steps=2, max_tokens=1000)
        self.assertEqual(len(stub.chat.completions.seen), 2)
        for seen in stub.chat.completions.seen:
            self.assertEqual(check_tool_pairing(seen), [])
        self.assertTrue(any(m.get("role") == "tool" for m in agent.history))


if __name__ == "__main__":
    unittest.main()
