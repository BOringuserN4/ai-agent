# -*- coding: utf-8 -*-
"""规划专题 · 陷阱探针 3：长任务 + 方差（2026/10/04）

前三陷阱（多部件/全局配对/六步）贪心 ReAct 全对 → 病未现。
本探针压两件事：
  · 更长的多派生量任务（6 城 → 峰值/谷值/中位数/高于平均名单）
  · 同一任务多跑，看 token/步数**方差**（稳定性是规划的另一价值）
"""
import os, re, sys, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TASK = (
    "请做一份『六城天气简报』：\n"
    "① 查询北京、上海、广州、深圳、杭州、成都 六个城市的当前气温；\n"
    "② 报出气温最高的城市、气温最低的城市；\n"
    "③ 报出这六个气温的**中位数**；\n"
    "④ 列出身高**高于平均气温**的城市名单；\n"
    "⑤ 用一句话总结：最高/最低/中位数/高于平均的城市。"
)
N = int(os.getenv("TRAP_N", "4"))


def check(ans):
    return {
        "含中位数": "中位" in ans,
        "含高于平均名单": ("高于平均" in ans or "超过平均" in ans),
        "含最高最低": ("最高" in ans and "最低" in ans),
        "含6城": sum(1 for c in ["北京","上海","广州","深圳","杭州","成都"] if c in ans) >= 5,
    }


if __name__ == "__main__":
    toks, calls, oks = [], [], 0
    for i in range(1, N + 1):
        a = Agent(system_prompt="你是一个善于使用工具的助手。")
        ans = a.run(TASK, max_steps=8) or ""
        t = [s.type for s in a.tracer.steps]
        c = t.count("tool_call"); tok = a.usage["total_tokens"]
        toks.append(tok); calls.append(c)
        chk = check(ans)
        ok = all(chk.values())
        oks += ok
        print(f"跑{i}: 工具调用={c} token={tok} 要素={chk} {'✅' if ok else '❌'}")
        print(f"   答: {ans.strip()[:150]}")
    print(f"\n=== 汇总 (n={N}) ===")
    print(f"要素全齐: {oks}/{N}")
    print(f"工具调用: {calls}  均值={statistics.mean(calls):.1f} 极差={max(calls)-min(calls)}")
    print(f"token   : {toks}  均值={statistics.mean(toks):.0f} 极差={max(toks)-min(toks)} 变异系数={(statistics.pstdev(toks)/statistics.mean(toks)):.2f}")
