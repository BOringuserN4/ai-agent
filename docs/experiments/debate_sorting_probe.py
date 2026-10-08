# -*- coding: utf-8 -*-
"""Debate 专题 · 探针：排序算法选型（2026/10/08）

场景（用户提出）：为嵌入式实时设备选排序算法。
争议点：快排 / 归并 / 堆排各有拥护者，需要 debate 出合适方案。

对比两臂：
  A 单 Agent：直接给建议（基线）
  B Debate ：三个主张者各挺一种算法 → 强制互相攻击 → 裁决

判定：用 6 条「本场景关键约束」打分（是否点到）——
  ① 近乎有序数据（快排退化风险 / Timsort 优势）
  ② 最坏情况可预测（实时要求）
  ③ 稳定性要求
  ④ 额外空间（嵌入式 256KB）
  ⑤ 缓存/常数因子
  ⑥ 明确给出可执行方案（不是「取决于」）
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

SCENARIO = (
    "场景：一台**嵌入式实时设备**要给约 **10 万条记录**排序。\n"
    "· 记录含「时间戳 + 业务字段」，数据**几乎已按时间有序**（新数据追加在尾部，偶有乱序）；\n"
    "· 设备 RAM 仅 **256 KB**；\n"
    "· 是**实时系统**：单次排序的**最坏情况耗时必须可预测**（超时即故障）；\n"
    "· 业务要求**稳定排序**（同一时间戳的记录保持原相对顺序）。\n"
)
QUESTION = "请从「快速排序 / 归并排序 / 堆排序」中选出最合适的方案，并说明理由与注意点。"

CRITERIA = {
    "①近乎有序": ("几乎已", "近乎有序", "接近有序", "已排序", "Timsort", "插入排序", "逆序可能性"),
    "②最坏可预测": ("最坏", "退化", "O(n²)", "O(n^2)", "可预测", "内省", "introsort"),
    "③稳定性": ("稳", "相对顺序"),
    "④空间": ("空间", "原地", "内存", "RAM", "256"),
    "⑤缓存/常数": ("缓存", "常数因子", "局部性", "分支预测"),
    "⑥给方案": ("建议", "方案", "推荐", "应该", "采用", "可以这样"),
}


def score(text):
    hit = {k: any(w in text for w in ws) for k, ws in CRITERIA.items()}
    return hit


def arm_single():
    a = Agent(system_prompt="你是资深系统工程师，给出明确的技术选型建议。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(f"{SCENARIO}\n{QUESTION}", max_steps=3) or ""
    return out.strip()


def arm_debate():
    roles = [
        ("快排派", "你主张**快速排序**。尽力论证它在本题的优势（平均最快、原地、缓存友好）。"),
        ("归并派", "你主张**归并排序**。尽力论证它（稳定、O(n log n) 保证、适合近乎有序用 Timsort）。"),
        ("堆排派", "你主张**堆排序**。尽力论证它（O(1) 额外空间、最坏 O(n log n) 保证、无递归深度风险）。"),
    ]
    transcript = []
    # 第 1 轮：各自立论
    for name, role in roles:
        ag = Agent(system_prompt=f"{role}\n一轮说完，简短。")
        with contextlib.redirect_stdout(io.StringIO()):
            out = ag.run(f"{SCENARIO}\n{QUESTION}\n\n轮到你（{name}）立论。", max_steps=2) or ""
        transcript.append((name, out.strip()))
    # 第 2 轮：强制互相攻击
    hist = "\n\n".join(f"【{n}】{t}" for n, t in transcript)
    for name, role in roles:
        ag = Agent(system_prompt=f"{role}\n现在**必须攻击其他两位**：指出他们方案的致命问题，并承认自己方案的一处短板。简短。")
        with contextlib.redirect_stdout(io.StringIO()):
            out = ag.run(f"{SCENARIO}\n\n【各方立论】\n{hist}\n\n轮到你（{name}）反驳。", max_steps=2) or ""
        transcript.append((name + "·反驳", out.strip()))
    # 裁决
    full = "\n\n".join(f"【{n}】{t}" for n, t in transcript)
    judge = Agent(system_prompt=(
        "你是中立技术决策者。综合各方论证，给出**一个明确的可执行方案**（不是「取决于」）。"
        "必须权衡：实时最坏情况、稳定性、内存、数据近乎有序。"))
    with contextlib.redirect_stdout(io.StringIO()):
        final = judge.run(f"{SCENARIO}\n\n【辩论全程】\n{full}\n\n{QUESTION}\n给出最终方案。",
                          max_steps=3) or ""
    return final.strip(), transcript


if __name__ == "__main__":
    print("=" * 68)
    print("Arm A · 单 Agent（基线）")
    print("=" * 68)
    a = arm_single()
    sa = score(a)
    print(a[:1200])
    print(f"\n[打分] 命中 {sum(sa.values())}/6：{ {k: ('✅' if v else '—') for k,v in sa.items()} }")

    print("\n" + "=" * 68)
    print("Arm B · Debate（三派立论 → 强制互攻 → 裁决）")
    print("=" * 68)
    b, tr = arm_debate()
    sb = score(b)
    print("\n—— 反驳轮摘录 ——")
    for n, t in tr:
        if "反驳" in n:
            print(f"\n【{n}】{t[:300]}")
    print("\n—— 最终方案 ——")
    print(b[:1200])
    print(f"\n[打分] 命中 {sum(sb.values())}/6：{ {k: ('✅' if v else '—') for k,v in sb.items()} }")

    print("\n" + "=" * 68)
    print(f"单 Agent: {sum(sa.values())}/6    Debate: {sum(sb.values())}/6")
