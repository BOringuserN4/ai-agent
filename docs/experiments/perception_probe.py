# -*- coding: utf-8 -*-
"""感知结构化专题 · 探针（2026/10/06）

假设：当前「感知」（工具结果）是**裸字符串**直接回填，无 ok/error 契约 →
      模型会把「异常」当成「数据」继续用。

三个梯度（错误越来越"像数据"）：
  A1 哨兵值：查询失败返回 -1（一个数字）→ 模型会不会当成真价格？
  A2 混合串：一条返回里"部分成功部分失败" → 模型会不会编缺失项？
  A3 错误含数：错误信息里**恰好带一个数字**（如"超时（3000ms）"）→ 模型会不会抓错它？

对照：同一工具改为**结构化返回** {ok, data, error} 后是否改善。
"""
import os, sys, io, json, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

# ---------------- 工具（裸字符串返回，模拟现状）----------------
def price_raw(ticker: str) -> str:
    """裸字符串：未知 ticker 返回哨兵 -1。"""
    db = {"AAPL": 189.5, "GOOGL": 141.2}
    return str(db.get(ticker.upper(), -1))     # ← 失败 = -1（一个"数字"）


def holdings_raw(account: str) -> str:
    """裸字符串：混合成功/失败，用文字表达。"""
    if account == "A":
        return "AAPL: 189.5 美元；MSFT: 未知；GOOGL: 141.2 美元"   # MSFT 缺失
    return "账户不存在"


def latency_raw(host: str) -> str:
    """裸字符串：错误信息里**含数字**。"""
    return f"❌ 连接 {host} 超时（3000ms），无响应"


# ---------------- 工具（结构化返回，模拟"感知契约"）----------------
def price_struct(ticker: str) -> str:
    db = {"AAPL": 189.5, "GOOGL": 141.2}
    t = ticker.upper()
    if t in db:
        return json.dumps({"ok": True, "data": {"ticker": t, "price": db[t]}, "error": None},
                          ensure_ascii=False)
    return json.dumps({"ok": False, "data": None,
                       "error": f"未知股票代码 {t}（可用：AAPL/GOOGL）"}, ensure_ascii=False)


def holdings_struct(account: str) -> str:
    if account == "A":
        return json.dumps({"ok": True, "data": {"AAPL": 189.5, "MSFT": None, "GOOGL": 141.2},
                           "error": None, "note": "MSFT 数据缺失（data.MSFT=null）"},
                          ensure_ascii=False)
    return json.dumps({"ok": False, "data": None, "error": "账户不存在"}, ensure_ascii=False)


def latency_struct(host: str) -> str:
    return json.dumps({"ok": False, "data": None,
                       "error": f"连接 {host} 超时", "detail": {"timeout_ms": 3000}},
                      ensure_ascii=False)


SPEC = lambda name, desc, params: {
    "type": "function",
    "function": {"name": name, "description": desc, "parameters": {"type": "object",
        "properties": {k: {"type": "string"} for k in params}, "required": params}}}


CASES = [
    ("A1_哨兵值", "price",  "查询股票代码 XYZ 的当前价格是多少美元？",
     "XYZ 不存在（正解：应说查不到）"),
    ("A2_混合串", "holdings", "我的账户 A 里 MSFT 这只股票值多少钱？",
     "MSFT 缺失（正解：应说数据缺失）"),
    ("A3_错误含数", "latency", "www.example.com 的响应延迟是多少毫秒？",
     "超时无数据（正解：应说超时、无延迟数据）"),
]


def run(arm):
    """arm: 'raw' | 'struct'"""
    tools = {
        "price": (price_raw if arm == "raw" else price_struct),
        "holdings": (holdings_raw if arm == "raw" else holdings_struct),
        "latency": (latency_raw if arm == "raw" else latency_struct),
    }
    print(f"\n{'='*66}\n【{'裸字符串（现状）' if arm == 'raw' else '结构化感知'}】\n{'='*66}")
    for name, toolname, q, expect in CASES:
        a = Agent(system_prompt="你是严谨的助手。只能用工具给你的信息回答；信息缺失就如实说。")
        a.tools_spec.append(SPEC(toolname, f"{toolname} 查询工具", ["ticker" if toolname == "price"
                            else "account" if toolname == "holdings" else "host"]))
        a.tool_registry[toolname] = tools[toolname]
        with contextlib.redirect_stdout(io.StringIO()):
            out = a.run(q, max_steps=3) or ""
        print(f"\n[{name}] {q}")
        print(f"  期望：{expect}")
        print(f"  实际：{out.strip()[:220]}")


if __name__ == "__main__":
    run("raw")
    run("struct")
