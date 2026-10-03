# -*- coding: utf-8 -*-
"""收尾步（ANSWER_STEP）落地后的回归测试（2026/10/03）

三层，缺一不可：
  T1 契约：确认「收尾步」真的不带工具（否则改了等于没改）
  T2 行为：链式任务下，ANSWER_STEP 开/关的硬停率差异（修复是否有效）
  T3 回归：普通可解任务**照常工作**，且成功路径**不额外调 LLM**（不砸坏别的）

运行：
    .venv/bin/python docs/experiments/regression_answer_step.py
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import agent.core as core
from agent.core import Agent
from docs.experiments.warn_ab_chain import NEXT_TOKEN_SPEC, next_token, TASK, CHAIN

N = int(os.getenv("REG_N", "10"))


def _mk_agent():
    a = Agent(system_prompt="你是一个严格的工具执行助手。")
    a.tools_spec.append(NEXT_TOKEN_SPEC)
    a.tool_registry["next_token"] = next_token
    return a


# ---------- T1 契约：收尾步不带工具 ----------
def t1_contract():
    calls = []
    a = _mk_agent()
    _real = a.client.chat.completions.create
    def spy(**kw):
        calls.append({"has_tools": kw.get("tools") is not None,
                      "tool_choice": kw.get("tool_choice")})
        return _real(**kw)
    a.client.chat.completions.create = spy
    a.run(TASK, max_steps=3)
    n = len(calls)
    ok = (n == 4                       # 3 工具轮 + 1 收尾步
          and all(c["has_tools"] for c in calls[:3])
          and not calls[-1]["has_tools"]
          and calls[-1]["tool_choice"] is None)
    print(f"T1 契约: LLM 调用 {n} 次; 前 3 次带工具={[c['has_tools'] for c in calls[:3]]}; "
          f"收尾步带工具={calls[-1]['has_tools'] if n else '?'} → {'✅ PASS' if ok else '❌ FAIL'}")
    return ok


# ---------- T2 行为：修复是否有效 ----------
def t2_behavior(answer_step: bool):
    core.ANSWER_STEP = answer_step
    hard = clean = 0
    for _ in range(N):
        a = _mk_agent()
        ans = a.run(TASK, max_steps=3) or ""
        if "已超过最大处理轮数" in ans:
            hard += 1
        if ans and "已超过最大处理轮数" not in ans and "DSML" not in ans:
            clean += 1
    return hard, clean


# ---------- T3 回归：普通任务照常 + 成功路径不额外调用 ----------
def t3_regression():
    calls = []
    a = Agent(system_prompt="你是一个善于使用工具的助手。")
    _real = a.client.chat.completions.create
    def spy(**kw):
        calls.append(1)
        return _real(**kw)
    a.client.chat.completions.create = spy
    ans = a.run("帮我算 123 * 456", max_steps=8) or ""
    ok_answer = "56088" in ans.replace(",", "")
    ok_calls = len(calls) <= 3        # 正常任务 2 次调用（1 工具 + 1 作答），绝不该到收尾步
    print(f"T3 回归: 答对 123*456={'✅' if ok_answer else '❌'}  回答={ans[:40]!r}  "
          f"LLM 调用={len(calls)}（成功路径应为 2）→ {'✅ PASS' if (ok_answer and ok_calls) else '❌ FAIL'}")
    return ok_answer and ok_calls


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print(f"令牌链正解: 第5步={CHAIN[5]}\n")
    ok1 = t1_contract()
    print()
    hard_on, clean_on = t2_behavior(True)
    hard_off, clean_off = t2_behavior(False)
    print(f"T2 行为 (链式任务, max_steps=3, N={N}):")
    print(f"   ANSWER_STEP=开: 硬停 {hard_on}/{N}   干净收敛 {clean_on}/{N}")
    print(f"   ANSWER_STEP=关: 硬停 {hard_off}/{N}   干净收敛 {clean_off}/{N}")
    print(f"   → {'✅ 修复有效' if clean_on > clean_off else '⚠️ 未见改善'}\n")
    ok3 = t3_regression()
    print()
    print("=" * 60)
    print(f"总评: T1={'PASS' if ok1 else 'FAIL'}  T2={'PASS' if clean_on > clean_off else 'FAIL'}  "
          f"T3={'PASS' if ok3 else 'FAIL'}")
