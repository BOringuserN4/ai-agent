# -*- coding: utf-8 -*-
"""
agent/tracing.py — 追踪器（可观测性核心）

作用：把 Agent 内部每一步「思考/调用工具/观察结果/回答」都记录下来，
形成一个结构化的"事件流水线"（轨迹），方便：
  1. 人类调试：看清 Agent 到底经历了什么
  2. 成本/用量核算：token、耗时
  3. 未来的可视化 Multi-Agent：把轨迹渲染成界面

这不是模型的一部分，纯粹是"录音机"。
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TraceStep:
    """轨迹里的一个步骤。"""
    type: str            # 事件类型：reason / tool_call / tool_result / answer
    detail: str          # 描述
    tool: Optional[str] = None
    args: Optional[dict] = None
    result: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


class Tracer:
    """记录 Agent 运行轨迹的"录音机"。"""

    def __init__(self):
        self.steps: List[TraceStep] = []

    def add(self, **kwargs):
        """添加一个步骤。"""
        step = TraceStep(**kwargs)
        self.steps.append(step)
        return step

    def log(self, msg: str, type: str = "reason"):
        """记录一条纯文字日志（思考/说明用）。"""
        self.add(type=type, detail=msg)

    def duration(self, start: float, **kwargs) -> TraceStep:
        """记录一个带耗时的步骤（start 为 time.time() 起点）。"""
        step = self.add(duration_ms=round((time.time() - start) * 1000, 1), **kwargs)
        return step

    def show(self):
        """把整条轨迹打印成人类可读文本。"""
        lines = ["\n════════ 运行轨迹 Trajectory ════════"]
        icons = {"reason": "🤔", "tool_call": "🛠️", "tool_result": "📦", "answer": "🤖"}
        for s in self.steps:
            icon = icons.get(s.type, "·")
            line = f"{icon} {s.detail}"
            if s.duration_ms is not None:
                line += f"  ({s.duration_ms}ms)"
            lines.append(line)
        lines.append("══════════════════════════════════")
        return "\n".join(lines)

    def summary(self) -> dict:
        """汇总：调用了几次工具、总耗时等。"""
        tool_calls = [s for s in self.steps if s.type == "tool_call"]
        total_ms = sum(s.duration_ms or 0 for s in self.steps)
        return {
            "steps": len(self.steps),
            "tool_calls": len(tool_calls),
            "total_ms": round(total_ms, 1),
        }
