# -*- coding: utf-8 -*-
"""规划专题 · 陷阱探针：现在的隐式 ReAct 会不会做砸？（2026/10/04）

目的：先证明"病"存在（否则规划是无病找药）。
设计意图（专打贪心 ReAct 的软肋）：
  · 跨步记忆：结尾要复用开头取到的时间
  · 依赖计算：平均值 → 再找"最偏离平均"的城市（依赖第一步结果）
  · 多部件输出：5 个要素，容易漏
  · 微妙计算：最偏离平均 ≠ 最高/最低

运行：.venv/bin/python docs/experiments/plan_trap_probe.py
"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

TASK = (
    "请依次完成下面 5 件事，最后只用一段话汇总：\n"
    "① 获取当前北京时间；\n"
    "② 查询北京、上海、广州、深圳、杭州 五个城市的当前气温；\n"
    "③ 算出这五个气温的平均值（保留 1 位小数）；\n"
    "④ 找出其中**气温最偏离平均值**的城市（即 |该市气温 − 平均值| 最大）；\n"
    "⑤ 汇总成一句话：现在是北京时间几点几分，五市平均气温 X.X 度，"
    "最偏离平均的是 Y 市（气温 Z 度）。"
)
N = int(os.getenv("TRAP_N", "3"))


def check(ans: str):
    """粗测：5 个要素是否齐（时间/五市气温/平均/最偏离城市/汇总句）。"""
    feats = {
        "含时间": bool(re.search(r"\d{1,2}[:：]\d{2}|\d{1,2}\s*点", ans)),
        "含平均": ("平均" in ans) and bool(re.search(r"\d+\.\d", ans)),
        "含最偏离城市": any(c in ans for c in ["北京", "上海", "广州", "深圳", "杭州"]) and
                        any(k in ans for k in ["偏离", "最远", "差距最大", "离平均"]),
        "含5市气温": sum(1 for c in ["北京", "上海", "广州", "深圳", "杭州"] if c in ans) >= 4,
    }
    return feats


if __name__ == "__main__":
    for i in range(1, N + 1):
        print(f"\n{'#'*70}\n# 第 {i}/{N} 跑\n{'#'*70}")
        a = Agent(system_prompt="你是一个善于使用工具的助手。")
        ans = a.run(TASK, max_steps=8) or ""
        types = [s.type for s in a.tracer.steps]
        print(f"\n[步数统计] 工具调用={types.count('tool_call')}  作答={types.count('answer')}  "
              f"总token={a.usage['total_tokens']}")
        print("[要素检查]", check(ans))
        print("[最终回答]\n" + ans.strip())
