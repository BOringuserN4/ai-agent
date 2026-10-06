# -*- coding: utf-8 -*-
"""去中心化协商专题 · 决定性实验 v3：随机真值（2026/10/06）

前几轮为何没打中：私有事实落在模型先验疆域内 → 集中式靠"通用判断"猜中。
本轮的杀手锏：**把真值随机化**。
  真值由随机数决定 → 模型再强也无从猜起（只能 ~50% 掷硬币）；
  而能把「分散私有事实」汇集起来的那一方 → 100%。

三个场景，每个随机真值、强制二选一：
  S1 发货仓：东仓 / 西仓（哪仓有货，随机）
  S2 变更窗口：02:00 / 04:00（哪个时段空闲，随机）
  S3 供应商：Alpha / Beta（哪家资质有效，随机）

两臂：
  集中式：单 Agent，只有问题 + 一个 lookup 工具（**返回访问受限**，模拟无权限）
  去中心化：共享频道，持事实的 Agent 发言 → 决策 Agent 据此收敛
"""
import os, sys, io, random, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TRIALS = int(os.getenv("TRIALS", "4"))
rng = random.Random(20261006)


def scenario(rng):
    """返回 (name, question, fact, truth, opts) —— truth 随机。

    ⚠️ 修正（2026/10/06）：真值是**正确选项** = opts[1-which]
    （事实说 opts[which] 有问题 → 应选另一个）。前一版把 truth 写成 opts[which]，
    导致「答对反而不匹配真值」，实验台翻车。
    """
    which = rng.choice([0, 1])
    kind = rng.choice(["wh", "slot", "vendor"])
    if kind == "wh":
        opts = ["东仓", "西仓"]
        truth = opts[1 - which]                 # ← 修正：有货的那个才是答案
        fact = (f"库存系统：{opts[which]} 无现货（补货最快 5 天）；"
                f"{opts[1 - which]} 有现货可立即出库。")
        q = ("订单 #A100 应从哪里发货？必须二选一：东仓 / 西仓。"
             "最后一行只写：答案=<选项>")
        return "发货仓", q, fact, truth, opts
    if kind == "slot":
        opts = ["02:00", "04:00"]
        truth = opts[1 - which]                 # ← 修正：空闲的那个
        fact = (f"变更日历：{opts[which]} 时段已被另一位工程师的不可打断操作占用（冲突）；"
                f"{opts[1 - which]} 时段空闲可选。")
        q = ("本次数据库变更安排在哪个窗口？必须二选一：02:00 / 04:00。"
             "最后一行只写：答案=<选项>")
        return "变更窗口", q, fact, truth, opts
    opts = ["Alpha", "Beta"]
    truth = opts[1 - which]                     # ← 修正：资质有效的那个
    fact = (f"合规记录：{opts[which]} 的资质证明已于昨日过期；"
            f"{opts[1 - which]} 的资质在有效期内。")
    q = ("选择哪家供应商？必须二选一：Alpha / Beta。"
         "最后一行只写：答案=<选项>")
    return "供应商", q, fact, truth, opts


def pick_of(text, opts):
    """优先解析『答案=X』标记；否则退回最后一个被提到的选项。"""
    import re
    m = re.search(r"答案\s*[=:：]\s*([^\s，,。\n]+)", text or "")
    if m:
        cand = m.group(1)
        for o in opts:
            if o in cand:
                return o
    found = [o for o in opts if o in (text or "")]
    return found[-1] if found else None      # 取最后提到的（通常是最终选择）


def arm_central(q, opts):
    a = Agent(system_prompt=(
        "你是决策者。可用一个 lookup 工具查询内部系统；若查不到，也必须给出二选一的答案。"))
    # 注入一个"访问受限"的查询工具，模拟权限边界
    a.tools_spec.append({"type": "function", "function": {
        "name": "lookup", "description": "查询内部系统记录。",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}},
                       "required": ["key"]}}})
    a.tool_registry["lookup"] = lambda key: "❌ 访问受限：该记录需要相应团队的授权。"
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(q, max_steps=3) or ""
    return out, pick_of(out, opts)


def arm_decentral(q, fact, opts):
    holder = Agent(system_prompt=f"你是信息持有者。你的私有信息：{fact}\n只陈述这条信息，简短。")
    with contextlib.redirect_stdout(io.StringIO()):
        msg = holder.run(f"{q}\n请把你掌握的、与决策相关的事实陈述出来。", max_steps=2) or ""
    decider = Agent(system_prompt="你是决策者。只根据收到的信息做二选一决定，简短。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = decider.run(f"{q}\n\n【来自相关团队的事实】\n{msg}\n\n给出你的二选一答案。", max_steps=2) or ""
    return out, pick_of(out, opts)


if __name__ == "__main__":
    c_hit = c_miss = c_none = 0
    d_hit = d_miss = d_none = 0
    print(f"{'场景':<10}{'真值':<8}{'集中式':<10}{'去中心化':<10}")
    print("-" * 46)
    for t in range(TRIALS):
        name, q, fact, truth, opts = scenario(rng)
        _, cp = arm_central(q, opts)
        _, dp = arm_decentral(q, fact, opts)
        c_res = "✅" if cp == truth else ("❌" if cp else "—")
        d_res = "✅" if dp == truth else ("❌" if dp else "—")
        c_hit += cp == truth; c_miss += (cp is not None and cp != truth); c_none += cp is None
        d_hit += dp == truth; d_miss += (dp is not None and dp != truth); d_none += dp is None
        print(f"{name:<10}{truth:<8}{c_res:<10}{d_res:<10}")
    n = TRIALS
    print("\n" + "=" * 46)
    print(f"集中式 : 命中 {c_hit}/{n}  错选 {c_miss}  未选 {c_none}   准确率 {c_hit/n:.0%}")
    print(f"去中心化: 命中 {d_hit}/{n}  错选 {d_miss}  未选 {d_none}   准确率 {d_hit/n:.0%}")
