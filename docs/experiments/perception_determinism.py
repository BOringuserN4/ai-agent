# -*- coding: utf-8 -*-
"""感知结构化专题 · 决定性实验：确定性消费（2026/10/06）

A 假设（模型把异常当数据）未打中——强模型能识破哨兵/未知/超时。
真边界推断：**能识破的是 LLM；下游代码识破不了。**

本实验用**纯代码消费**同一份感知（不经 LLM）：
  · 裸字符串 + 正则解析 → 遇到「格式漂移」或「哨兵值」就崩 / 算错
  · 结构化 JSON → 稳定、可分支

两个子实验：
  D1 格式漂移：同一工具 3 种等价写法，针对格式#1 写的正则能否解析 #2/#3？
  D2 哨兵/错误：把 -1 当价格参与计算 → 总价算错；结构化能 ok=false 分支。
"""
import json, re

# ---------------- D1：格式漂移 ----------------
VARIANTS = [
    "AAPL: 189.5; GOOGL: 141.2",        # 格式#1（解析器按此写）
    "AAPL 189.5 美元；GOOGL 141.2 美元",  # 格式#2（等价，换了标点/单位）
    "价格 AAPL=189.5 | 价格 GOOGL=141.2", # 格式#3（等价，换了分隔词序）
]

def parse_raw_d1(s):
    """针对格式#1 写的正则：'TICKER: 价格'"""
    return {m.group(1): float(m.group(2))
            for m in re.finditer(r"([A-Z]+):\s*([\d.]+)", s)}

def parse_struct_d1(s):
    """结构化：字段固定，格式无关。"""
    try:
        d = json.loads(s)
    except Exception:
        return None
    if not d.get("ok"):
        return None
    return d.get("data") or {}

STRUCT_D1 = [
    json.dumps({"ok": True, "data": {"AAPL": 189.5, "GOOGL": 141.2}}),
    json.dumps({"ok": True, "data": {"AAPL": 189.5, "GOOGL": 141.2}}),
    json.dumps({"ok": True, "data": {"AAPL": 189.5, "GOOGL": 141.2}}),
]

# ---------------- D2：哨兵/错误参与计算 ----------------
RAW_FAIL = "-1"                                     # 裸字符串：失败=哨兵数字
STRUCT_FAIL = json.dumps({"ok": False, "data": None, "error": "未知代码"})

def total_raw(s, qty=10):
    """下游程序：把返回值当价格 → 总价。"""
    try:
        price = float(s)
    except ValueError:
        return "解析失败"
    return price * qty          # ← -1 * 10 = -10，静默算错

def total_struct(s, qty=10):
    d = json.loads(s)
    if not d.get("ok"):
        return f"无法计算（{d.get('error')}）"   # ← 正确分支
    return d["data"]["price"] * qty


if __name__ == "__main__":
    print("=" * 64)
    print("D1 · 格式漂移：同一份数据、3 种等价写法")
    print("=" * 64)
    print(f"{'写法':<34}{'裸正则解析':<20}{'结构化解析'}")
    for i, s in enumerate(VARIANTS):
        r = parse_raw_d1(s)
        st = parse_struct_d1(STRUCT_D1[i])
        mark = "✅" if len(r) == 2 else "❌ 崩/漏"
        print(f"{s[:32]:<34}{str(r)[:18]:<20}{'✅ ' + str(st)}" if st else
              f"{s[:32]:<34}{mark + ' ' + str(r)[:14]:<20}结构化失败")
    print("\n判据：针对格式#1 写的正则，在 #2/#3 上崩（返回空）。\n")

    print("=" * 64)
    print("D2 · 失败参与计算（下游代码，无 LLM 把关）")
    print("=" * 64)
    print(f"裸字符串 -1  → 总价 = {total_raw(RAW_FAIL)}   ← ❌ 静默算错（负价格）")
    print(f"结构化失败    → {total_struct(STRUCT_FAIL)}   ← ✅ 正确分支")
