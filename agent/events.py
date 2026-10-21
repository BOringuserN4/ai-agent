"""最小事件层：把 Agent 的关键动作写成可回放的事件。

设计原则：
- 事件是事实，不是解释；UI 只做渲染。
- 默认 NullSink，不开启时零开销。
- 一条事件一行 JSONL，方便回放、测试和分享。
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

EVENT_VERSION = 1


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def new_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"r-{stamp}-{uuid.uuid4().hex[:4]}"


class NullSink:
    """不写任何东西；默认关闭时使用。"""

    def __call__(self, event: dict) -> None:
        return None


class MemorySink:
    """把事件留在内存里，方便测试或临时预览。"""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)


class JsonlSink:
    """每个事件写一行 JSONL。"""

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        # 先清空，避免追加到上一次的 trace
        open(path, "w", encoding="utf-8").close()
        self._lock = threading.Lock()

    def __call__(self, event: dict) -> None:
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
                f.flush()


class EventBus:
    """一个很小的发布者：生成事件、递增序号、分发给 sink。"""

    def __init__(self, run_id: str | None = None, sinks: list[Callable] | None = None) -> None:
        self.run_id = run_id or new_run_id()
        self.sinks = sinks or [NullSink()]
        self.seq = 0
        self._lock = threading.Lock()

    def emit(
        self,
        type: str,
        payload: dict[str, Any] | None = None,
        *,
        step: int = 0,
        span_id: str | None = None,
        parent_id: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> dict:
        with self._lock:
            self.seq += 1
            event = {
                "v": EVENT_VERSION,
                "run_id": self.run_id,
                "seq": self.seq,
                "ts": now_iso(),
                "type": type,
                "step": step,
                "span_id": span_id or f"s-{self.seq:04d}",
                "parent_id": parent_id,
                "payload": payload or {},
                "usage": usage,
            }
        for sink in self.sinks:
            sink(event)
        return event
