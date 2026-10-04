# -*- coding: utf-8 -*-
"""规划专题 · 边界钉死：长依赖链 vs 规划（2026/10/04）

决策 2：造工具，把「规划救不了的那条界」实测坐实。

工具：chain_next(tok) —— 不可预测的令牌链，每步输入 = 上一步输出，
       **结构上无法批量**（下一 token 必须等上一 token 回来）。

对照：
  · 贪心臂：直接执行
  · 规划臂：**先让 LLM 生成一份步骤计划**，再带着计划执行（最小 Planner-Executor）

扫描：链长 N（N=5 在预算内 / N=12 超预算），max_steps=8。

预期（待验证）：N=5 两臂都成；N=12 两臂都**败** → 规划无法变出预算。
"""
import os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

# ---- 20 步随机令牌链（固定种子，可复现）----
_rng = random.Random(20261004)
_AL = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CHAIN = ["S7K"] + ["".join(_rng.choice(_AL) for _ in range(3)) for _ in range(20)]
NEXT = {CHAIN[i]: CHAIN[i + 1] for i in range(len(CHAIN) - 1)}


def chain_next(tok: str) -> str:
    return NEXT.get((tok or "").strip().upper(), "ERR_NOT_FOUND")


CHAIN_SPEC = {"type": "function", "function": {
    "name": "chain_next",
    "description": "令牌链推进：输入当前令牌，返回链中下一个。令牌为随机串，无法跳过或预知。",
    "parameters": {"type": "object", "properties": {"tok": {"type": "string"}}, "required": ["tok"]}}}


def make_plan(task: str) -> str:
    """最小 Planner：让 LLM 先把任务拆成有序原子步骤。"""
    from openai import OpenAI
    c = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    resp = c.chat.completions.create(
        model="deepseek-flash",
        messages=[{"role": "system", "content":
                   "你是任务规划器。把任务拆成有序的原子步骤，每步一句话，只输出编号列表，不要解释。"},
                  {"role": "user", "content": task}],
        temperature=0, max_tokens=400)
    return (resp.choices[0].message.content or "").strip()


def run_arm(n_steps: int, use_plan: bool):
    task = (f"链式任务：从起始令牌 {CHAIN[0]} 出发，连续调用 chain_next 前进 {n_steps} 步"
            f"（每次把上一次结果作为下一次输入），最后报告第 {n_steps} 步得到的令牌。")
    a = Agent(system_prompt="你是一个严格执行步骤的工具助手。")
    a.tools_spec.append(CHAIN_SPEC)
    a.tool_registry["chain_next"] = chain_next

    plan = ""
    if use_plan:
        plan = make_plan(task)
        a._base_system += "\n\n【已制定计划，请照此执行】\n" + plan

    ans = a.run(task, max_steps=8) or ""
    calls = [s.tool for s in a.tracer.steps if s.type == "tool_call"]
    target = CHAIN[n_steps]
    return {
        "n_steps": n_steps, "use_plan": use_plan, "plan": plan,
        "tool_calls": len(calls),
        "reached": target in ans.replace("`", ""),
        "target": target,
        "hard_stop": "已超过最大处理轮数" in ans,
        "tokens": a.usage["total_tokens"],
    }


if __name__ == "__main__":
    print(f"链：{' → '.join(CHAIN[:7])} ... （共 21 个令牌）\n")
    rows = []
    for n in (5, 12):
        for up in (False, True):
            r = run_arm(n, up)
            rows.append(r)
            tag = "规划臂" if up else "贪心臂"
            print(f"[N={n:2d} {tag}] 工具调用={r['tool_calls']:2d} "
                  f"达成={r['reached']} 硬停={r['hard_stop']} token={r['tokens']}")
            if up:
                print(f"        计划预览：{r['plan'][:80].replace(chr(10), ' / ')}...")
    print("\n" + "=" * 62)
    print(f"{'N':<5}{'臂':<8}{'工具调用':<10}{'达成':<8}{'硬停':<8}token")
    print("-" * 62)
    for r in rows:
        print(f"{r['n_steps']:<5}{'规划' if r['use_plan'] else '贪心':<8}"
              f"{r['tool_calls']:<10}{str(r['reached']):<8}{str(r['hard_stop']):<8}{r['tokens']}")
