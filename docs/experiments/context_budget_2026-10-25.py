from types import SimpleNamespace
from agent.core import Agent

def est_msg(m):
    # 比旧版多算：角色/结构开销 + tool_calls arguments
    n = 4 + max(1, len(str(m.get("content", "") or "")) // 2)
    for tc in m.get("tool_calls", []) or []:
        fn = tc.get("function", {}) if isinstance(tc, dict) else {}
        n += 4 + max(1, len(str(fn.get("arguments", ""))) // 2)
    return n

def est(msgs): return sum(est_msg(m) for m in msgs)

def group_turns(history):
    """system + 以 user 开头、包含后续 assistant/tool 的完整 turn。"""
    system = history[0] if history and history[0].get("role") == "system" else None
    turns, cur = [], None
    for m in history[1:]:
        if m.get("role") == "user":
            if cur: turns.append(cur)
            cur = [m]
        else:
            if cur is None: cur = [m]  # 防御：非 user 开头也成组
            else: cur.append(m)
    if cur: turns.append(cur)
    return system, turns

def fit_history(history, max_tokens):
    """在构造请求前裁剪；保留 system + 最新完整 turn，绝不拆 tool 配对。"""
    system, turns = group_turns(history)
    kept = list(turns)
    while len(kept) > 1 and est(([system] if system else []) + [m for t in kept for m in t]) > max_tokens:
        kept.pop(0)
    body = [m for t in kept for m in t]
    msgs = ([system] if system else []) + body
    return msgs, est(msgs), len(kept)

class Stub:
    class chat:
        class completions:
            seen=None
            @classmethod
            def create(cls, **kw):
                cls.seen = kw.get("messages", [])
                msg = SimpleNamespace(content="done", tool_calls=None)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                                       usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2))

# 1) 长历史：旧请求 vs 新请求
a = Agent(client=Stub(), tools=("calculator",))
a.history=[{"role":"system","content":"你是助手。"}]
for i in range(12):
    a.history += [{"role":"user","content":f"第{i}轮："+"历史"*80},
                  {"role":"assistant","content":f"回答{i}："+"内容"*80}]
a.history.append({"role":"user","content":"现在的新问题"})
old_msgs = a.history[:]  # 旧版在 trim 前构建的请求
a.trim_history(max_tokens=200)
print("旧版: 请求 est", est(old_msgs), "-> history 后 est", est(a.history))
new_msgs, new_est, n_turns = fit_history(a.history, max_tokens=200)
print("新版: 请求 est", new_est, "turns kept", n_turns, "messages", len(new_msgs))
print("新版保留当前问题?", any("现在的新问题" in str(m.get("content","")) for m in new_msgs))
print("新版保留最早一轮?", any("第0轮" in str(m.get("content","")) for m in new_msgs))

# 2) 工具配对：旧版可能留孤儿 tool；新版整轮保留/丢弃
tool_history=[
 {"role":"system","content":"sys"},
 {"role":"user","content":"u"*100},
 {"role":"assistant","content":"","tool_calls":[{"id":"c1","type":"function","function":{"name":"calculator","arguments":"{}"}}]},
 {"role":"tool","tool_call_id":"c1","content":"r"*100},
 {"role":"assistant","content":"a"*100},
]
b = Agent(client=Stub(), tools=("calculator",)); b.history=[dict(m) for m in tool_history]
b.trim_history(max_tokens=101)
print("旧版工具裁剪:", [(m["role"], "tool_calls" in m, m.get("tool_call_id")) for m in b.history])
new_msgs, new_est, n_turns = fit_history(tool_history, max_tokens=101)
print("新版工具裁剪:", [(m["role"], "tool_calls" in m, m.get("tool_call_id")) for m in new_msgs], "est", new_est)
print("新版是否留孤儿 tool?", any(m.get("role")=="tool" for m in new_msgs) and not any("tool_calls" in m for m in new_msgs))
