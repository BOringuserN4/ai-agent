"""上下文工程实验 · 2026-10-25（修复后版）

前两节用局部函数复现旧实现（历史证据），后两节验证修复后的 Agent。
不调 API，用 stub client 截获请求。
"""
from types import SimpleNamespace

from agent.core import Agent
from agent.context_budget import (
    estimate_messages, estimate_text, fit_to_budget, check_tool_pairing,
)


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


def old_est(messages):
    # 旧版：只算 content，中文按 2 字 1 token
    return sum(max(1, len(str(m.get("content", "") or "")) // 2) for m in messages)


def old_trim(history, max_tokens):
    """旧实现：逐条 pop，且不检查 tool 配对。"""
    while len(history) > 2:
        total = old_est(history)
        if total <= max_tokens:
            break
        for i, m in enumerate(history):
            if m["role"] != "system":
                history.pop(i)
                break


def base_history():
    h = [{"role": "system", "content": "你是助手。"}]
    for i in range(12):
        h += [
            {"role": "user", "content": f"第{i}轮：" + "历史" * 80},
            {"role": "assistant", "content": f"回答{i}：" + "内容" * 80},
        ]
    return h


def with_current():
    h = base_history()
    h.append({"role": "user", "content": "现在的新问题"})
    return h


def main():
    print("== 1) 旧版：请求前 / 请求后 ==")
    h = with_current()
    old_request = list(h)          # 旧版先构造 request
    old_trim(h, max_tokens=200)    # 再裁 history
    print("request messages:", len(old_request), "old_est:", old_est(old_request))
    print("history after trim:", len(h), "old_est:", old_est(h))
    print("request > 200?", old_est(old_request) > 200,
          "| contains oldest?", any("第0轮" in str(m.get("content", "")) for m in old_request))

    print("\n== 2) 新版：请求前按整 turn 裁剪 ==")
    r = fit_to_budget(with_current(), max_tokens=200)
    print(r.summary())
    print("contains current?", any("现在的新问题" in str(m.get("content", "")) for m in r.messages),
          "| contains oldest?", any("第0轮" in str(m.get("content", "")) for m in r.messages))

    print("\n== 3) tool 配对 ==")
    tool_history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u" * 100},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "calculator", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": "r" * 100},
        {"role": "assistant", "content": "a" * 100},
    ]
    old = [dict(m) for m in tool_history]
    old_trim(old, max_tokens=101)
    print("old:", [(m["role"], bool(m.get("tool_calls")), m.get("tool_call_id")) for m in old])
    print("old issues:", check_tool_pairing(old))
    new = fit_to_budget(tool_history, max_tokens=101)
    print("new:", [(m["role"], bool(m.get("tool_calls")), m.get("tool_call_id")) for m in new.messages])
    print("new summary:", new.summary())

    print("\n== 4) 修复后的 Agent：request 真的受预算约束 ==")
    stub = StubClient()
    a = Agent(client=stub, tools=("calculator",))
    a.history = base_history()       # run 会追加当前问题
    a.run("现在的新问题", max_steps=1, max_tokens=200)
    seen = stub.chat.completions.seen
    print("request messages:", len(seen), "new_est:", estimate_messages(seen))
    print("request <= 200?", estimate_messages(seen) <= 200,
          "| contains current?", any("现在的新问题" in str(m.get("content", "")) for m in seen),
          "| contains oldest?", any("第0轮" in str(m.get("content", "")) for m in seen))

    print("\n== 5) 估算器：同一段中文 ==")
    sample = "用户问的是上下文预算，为什么历史会爆炸，以及裁剪应该按什么单位。"
    print("chars:", len(sample), "old:", max(1, len(sample) // 2), "new:", estimate_text(sample))


if __name__ == "__main__":
    main()
