# -*- coding: utf-8 -*-
"""验证：预算预警文案是否真的进了 prompt？（2026/10/03）

疑点：warn_ab_chain.py 里 WARN=2 与 WARN=0 的总 token 只差 1（2383 vs 2382），
但预警文案 ~70 字、应注入 2 次 → 本该差 ~140。先查它到底注入没有。
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import agent.core as core
from agent.core import Agent
from docs.experiments.warn_ab_chain import NEXT_TOKEN_SPEC, next_token, TASK

core.REMAINING_STEPS_WARN = int(os.getenv("DBG_WARN", "2"))
a = Agent(system_prompt="你是一个严格的工具执行助手。")
a.tools_spec.append(NEXT_TOKEN_SPEC)
a.tool_registry["next_token"] = next_token

rounds = []
_real = a.client.chat.completions.create
def spy(**kw):
    sysmsg = kw["messages"][0]["content"]
    rounds.append({
        "has_warn": "剩余工具调用次数不多" in sysmsg,
        "system_len": len(sysmsg),
    })
    r = _real(**kw)
    rounds[-1]["prompt_tokens"] = r.usage.prompt_tokens
    return r
a.client.chat.completions.create = spy

a.run(TASK, max_steps=3)

print(f"\n===== 每轮 prompt 检查（WARN={core.REMAINING_STEPS_WARN}, max_steps=3）=====")
for i, r in enumerate(rounds):
    print(f"第 {i+1} 步(remaining={3-i}): 含预警={r['has_warn']}  "
          f"system长度={r['system_len']}  prompt_tokens={r['prompt_tokens']}")
print(f"\n预警注入轮数: {sum(r['has_warn'] for r in rounds)} / {len(rounds)}")
