# -*- coding: utf-8 -*-
"""感知结构化契约 · 落地验证（2026/10/06）

验三件事：
  T1 契约生成：工具失败/成功 → observation 的 ok 正确（旧字符串工具靠启发式，标记 _normalized）
  T2 确定性消费：下游程序据此分支，不再静默算错（对照 perception_determinism.py 的 D2）
  T3 无回归：普通可解任务照常；成功路径行为不变
"""
import os, sys, io, json, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent
from agent.observation import ok, fail, normalize, is_observation

SPEC = lambda name, p: {"type": "function", "function": {
    "name": name, "description": "查询", "parameters": {"type": "object",
    "properties": {p: {"type": "string"}}, "required": [p]}}}


def run(toolname, param, fn, q):
    a = Agent(system_prompt="你是助手。")
    a.tools_spec.append(SPEC(toolname, param))
    a.tool_registry[toolname] = fn
    with contextlib.redirect_stdout(io.StringIO()):
        a.run(q, max_steps=3)
    return [s.observation for s in a.tracer.steps if s.type == "tool_result"]


if __name__ == "__main__":
    print("=" * 60)
    print("T1 · 契约生成")
    print("=" * 60)
    # 新式工具（显式 ok/fail）
    new_obs = run("price", "ticker", lambda ticker: fail("未知代码", _normalized=False)
                  if ticker == "XYZ" else ok({"price": 189.5}),
                  "查 XYZ 价格")
    print("新式工具(显式 fail):", new_obs[0])
    # 旧式工具（裸字符串，启发式）
    old_obs = run("old", "x", lambda x: "❌ 查询失败", "查 x")
    print("旧式工具(裸字符串):", old_obs[0])
    # 成功
    ok_obs = run("calc", "e", lambda e: "42", "算 42")
    print("成功:", ok_obs[0])
    t1 = (new_obs[0]["ok"] is False and old_obs[0]["ok"] is False
          and ok_obs[0]["ok"] is True)
    print(f"→ T1 {'✅ PASS' if t1 else '❌ FAIL'}\n")

    print("=" * 60)
    print("T2 · 确定性消费（下游代码分支，对照 D2）")
    print("=" * 60)
    obs_fail = run("price", "ticker", lambda ticker: fail("未知代码"), "查 XYZ")[0]
    # 下游程序：若按契约 → 正确分支；若旧式把 -1 当价格 → -10
    if is_observation(obs_fail) and not obs_fail["ok"]:
        downstream = f"无法计算（{obs_fail['error']}）"
    else:
        downstream = "（旧式）把返回值当价格算 → 静默算错"
    print("下游消费结果:", downstream)
    t2 = "无法计算" in downstream
    print(f"→ T2 {'✅ PASS（正确分支，不再静默算错）' if t2 else '❌ FAIL'}\n")

    print("=" * 60)
    print("T3 · 无回归（普通任务）")
    print("=" * 60)
    a = Agent(system_prompt="你是助手。")
    with contextlib.redirect_stdout(io.StringIO()):
        ans = a.run("帮我算 123*456", max_steps=4) or ""
    t3 = "56088" in ans
    print(f"123*456 = {'✅' if t3 else '❌'}  答案: {ans.strip()[:40]}")
    print(f"→ T3 {'✅ PASS' if t3 else '❌ FAIL'}")
    print("\n" + "=" * 60)
    print(f"总评: T1={'PASS' if t1 else 'FAIL'}  T2={'PASS' if t2 else 'FAIL'}  T3={'PASS' if t3 else 'FAIL'}")
