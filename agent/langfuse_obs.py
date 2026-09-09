# -*- coding: utf-8 -*-
"""
agent/langfuse_obs.py — Langfuse 可观测性封装（第 10 周）

作用：把项目现有的「自实现 Tracer（只打印到终端）」升级为
      「Langfuse 平台级可观测性（网页看板：追踪/成本/提示词）」。

设计原则（与 memory.py 升级一致）：
  - 对外尽量「零侵入」：core.py / multi_agent.py 的 Agent 逻辑不改，
    只在入口处多一层可选的 trace 包装。
  - 有 LANGfuse key 就启用，没有就优雅降级（打印提示，不阻塞主流程）。
  - 埋点粒度和现有 Tracer.steps 对齐：reason / tool_call / tool_result / answer。

用法：
  from agent.langfuse_obs import get_langfuse, agent_trace

  # 1) 显式初始化（读 .env: LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST）
  lf = get_langfuse()

  # 2) 包装一次 Agent 调用
  with agent_trace(name="agent-run", user_id="demo", input_text=user_input) as trace:
      answer = agent.run(user_input)   # 完整 Agent 循环被包成一条 trace
      trace.add_output(answer)

依赖：
  pip install langfuse   （已装 4.15.1）
"""
import os
import time
from contextlib import contextmanager

_secret_keys = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
_required_keys = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")

def _host() -> str:
    """Langfuse 服务地址。兼容 LANGFUSE_BASE_URL / LANGFUSE_HOST，默认本地。"""
    return (os.getenv("LANGFUSE_BASE_URL")
            or os.getenv("LANGFUSE_HOST")
            or "http://localhost:3000")


def _config_ready() -> bool:
    """判断 .env 里是否配好了 Langfuse 的三要素（公钥/私钥/host）。
    未配置时返回 False，调用方据此优雅降级，不报错、不阻塞。"""
    vals = [os.getenv(k) for k in _required_keys]
    return all(v and v not in ("", "your_...") for v in vals)


def get_langfuse():
    """惰性初始化 Langfuse 客户端。

    - 已配置：返回 Langfuse 实例。
    - 未配置：返回 None（调用方用 if 判断，避免 import 报错拖垮主流程）。
    """
    if not _config_ready():
        return None
    try:
        from langfuse import Langfuse
        return Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=_host(),
            # 关键：Langfuse v4 需要该 header 才能把 OTel span 实时转成 traces/observations
            additional_headers={"x-langfuse-ingestion-version": "4"},
        )
    except Exception:
        # 即使 SDK 有问题也不影响主对话
        return None


@contextmanager
def agent_trace(name="agent.run", user_id=None, input_text=None, metadata=None):
    """把一段 Agent 执行包成一条 Langfuse Trace。

    这是核心埋点：进入时开 trace，退出时（含异常）自动关闭并上报。
    生成（LLM/工具调用）由调用方用 trace.span 追加，见 agent_traced_run。

    Args:
        name: trace 名称，如 "agent-run" / "math-expert"
        user_id: 可选，标识用户（对应 Langfuse 的 session 维度的 user）
        input_text: 用户输入，作为 trace 的 input 字段
        metadata: 可选 dict，附加到 trace 元数据

    Yields:
        lf 实例（可能为 None，若未配置则静默降级）
    """
    lf = get_langfuse()
    if lf is None:
        # 未配置：直接用空上下文，客户端代码 if lf 分支会跳过上报
        yield None
        return

    started = time.time()
    trace = lf.trace(
        name=name,
        user_id=user_id,
        input=input_text,
        metadata=metadata or {},
    )
    try:
        yield lf
        trace.update(output="done")
    except Exception as e:
        trace.update(output=f"error: {e}")
        raise
    finally:
        # 上报耗时
        try:
            trace.update(
                metadata={**(metadata or {}), "elapsed_ms": round((time.time() - started) * 1000, 1)}
            )
        except Exception:
            pass


def span_from_trace_step(lf, trace, step):
    """把现有 Tracer 的一个 step 映射成 Langfuse 的一个 span（可选辅助）。

    现有 Tracer.steps 里每个 TraceStep 字段：type/detail/tool/args/result/duration_ms。
    Langfuse span 需要：name, input, output, start/end 或 手动。

    Args:
        lf: Langfuse 实例（None 则跳过）
        trace: Langfuse trace 对象
        step: 现有 Tracer 的 TraceStep
    """
    if lf is None or trace is None:
        return
    try:
        span = trace.span(
            name=(step.tool or step.type),
            input={"detail": step.detail, "args": step.args},
            output=step.result,
            start_time=step.timestamp,
            end_time=(step.timestamp + (step.duration_ms or 0) / 1000.0),
        )
        return span
    except Exception:
        # 埋点失败不影响主流程
        return None
