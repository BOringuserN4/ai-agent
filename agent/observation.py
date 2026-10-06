# -*- coding: utf-8 -*-
"""agent/observation.py — 感知（Observation）结构化契约

为什么需要它（实测依据，见 docs/01-基础章/perception-structured-investigation.md）：
  当前工具结果是**裸字符串**直接回填。LLM 消费时强模型能识破哨兵/缺失/超时，
  但**下游程序**消费时不行：
    · 格式漂移 → 针对旧格式写的正则遇等价写法**静默返回空**；
    · 失败哨兵（如 -1）参与计算 → **静默算错**（−1×10 = −10）。
  → 感知一旦要交给**程序**（Pipeline / Evaluator-Critic / 外部系统），
    就必须有**确定性契约**，不能靠"模型会识破"。

契约形态：
    {"ok": bool, "data": Any, "error": str | None, ...}
  · ok=True  → data 为结果，error 为 None
  · ok=False → error 说明原因，data 可以为 None
  · 额外键（如 elapsed_ms、truncated）为**可选**元信息，消费方不应依赖

⚠️ 确定性边界（重要）：
  契约**只在生产者遵守时才确定**。旧工具若仍返回裸字符串，
  `normalize()` 只能**启发式**判断成败，并标 `_normalized=True` 提示
  "这里走了有损路径"。→ 想真正确定，就得改工具去返回 ok()/fail()。
"""
from typing import Any, Optional

# 明确的成败标记（生产者可用）
STATUS_OK = "ok"
STATUS_ERROR = "error"

# 启发式失败信号（仅用于兼容旧字符串工具；新工具请直接用 fail()）
_ERROR_MARKERS = ("❌", "错误", "失败", "error", "Error", "未找到", "暂不支持", "异常")


def ok(data: Any = None, **meta) -> dict:
    """构造成功的 Observation。"""
    return {"ok": True, "data": data, "error": None, **meta}


def fail(error: Any, data: Any = None, **meta) -> dict:
    """构造失败的 Observation。"""
    return {"ok": False, "data": data, "error": str(error), **meta}


def is_observation(x: Any) -> bool:
    """判断一个值是否已是 Observation（含 ok + data 键且 ok 为布尔）。"""
    return isinstance(x, dict) and isinstance(x.get("ok"), bool) and "data" in x


def normalize(result: Any, *, tool: str = None) -> dict:
    """把任意工具返回**归一化**为 Observation。

    规则：
      · 已是 Observation      → 原样返回（补齐 error 键）
      · dict（非 Observation）→ 包成 ok(dict)
      · str：
          - 命中失败标记         → fail(str)
          - 否则                → ok(str)
      · None                   → ok(None)
      · 其它类型               → ok(value)

    兼容旧工具时，会在结果里加 `_normalized=True`（提示"有损推断"），
    消费方可据此决定是否信任 `ok`。
    """
    if is_observation(result):
        result.setdefault("error", None)
        return result
    if isinstance(result, dict):
        return ok(result, _normalized=True)
    if result is None:
        return ok(None, _normalized=True)
    if isinstance(result, str):
        if any(m in result for m in _ERROR_MARKERS):
            return fail(result, _normalized=True)
        return ok(result, _normalized=True)
    return ok(result, _normalized=True)


def parse_error(text: str) -> Optional[str]:
    """从裸字符串里尽力提取错误信息（兼容旧工具，可选）。"""
    for m in _ERROR_MARKERS:
        if m in text:
            return text.strip()
    return None
