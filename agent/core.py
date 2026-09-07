# -*- coding: utf-8 -*-
"""
agent/core.py — Agent 核心引擎

主语：
- 管理对话历史（多轮聊天）。
- 把「模型 + 工具声明 + 工具执行」串成 ReAct 循环。
- 用 Tracer 记录每一步（可观测性）。
- 记录 token 用量（成本核算）。
- 加上下文预算控制，防止 history 无限膨胀。

设计原则：
- 工具声明与真实函数来自 agent.tools，模块化。
- 支持多轮对话：持续把历史追加进 messages。
- ReAct 循环有 max_steps 兜底，防止死循环。
"""
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
from agent.tools import get_tools_spec, get_tool_registry
from agent.tracing import Tracer

load_dotenv()


def get_api_key():
    import os
    return os.getenv("DEEPSEEK_API_KEY", "")


class Agent:
    def __init__(self, system_prompt="你是一个乐于助人的 AI 助手。", tools=None, memory=None):
        """
        Args:
            system_prompt: 这个 Agent 的人格/角色说明。
            tools: 可选。限定这个 Agent 能用哪些工具，如 ("calculator",
                   "get_weather")。不传则默认用全部工具。
            memory: 可选。传一个 agent.memory.MemoryStore 实例，则启用长期记忆。
                   会：提问前检索相关历史，回答后写入重要信息。
        """
        key = get_api_key()
        if not key or len(key) < 10:
            raise SystemExit("❌ 请先配置 .env 里的 DEEPSEEK_API_KEY")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        self.tools = set(tools) if tools else None  # None=全部
        self.tools_spec = self._filter_spec(get_tools_spec())
        self.tool_registry = self._filter_registry(get_tool_registry())
        self.memory = memory  # 长期记忆库（可为 None）
        # 原始系统提示（记得它，注入记忆时动态构造，不污染 history）
        self._base_system = system_prompt
        # 对话历史：开头放系统提示
        self.history = [{"role": "system", "content": system_prompt}]
        # 追踪器：记录本轮运行足迹
        self.tracer = Tracer()
        # 用量统计：本轮累计 token
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _filter_spec(self, spec):
        """按 self.tools 限定，只保留允许的工具声明。"""
        if not self.tools:
            return spec
        return [s for s in spec if s["function"]["name"] in self.tools]

    def _filter_registry(self, registry):
        """按 self.tools 限定，只保留允许的工具执行函数。"""
        if not self.tools:
            return registry
        return {k: v for k, v in registry.items() if k in self.tools}

    def reset(self):
        """清空对话历史，但保留系统提示。"""
        self.history = [self.history[0]]

    # ---- 上下文预算控制 ----
    def trim_history(self, max_tokens: int = 6000):
        """当历史太长时，精简掉旧消息，只保留最近若干条 + 系统提示。

        简单策略：若估计 token 超过上限，就丢弃中间较旧的轮次。
        生产级会用更智能的压缩/摘要，这里先做基础版。
        """
        # 粗略估计 token 数（中文约 1 字≈1 token，英文约 4 字符≈1 token）
        def est_tokens(text: str) -> int:
            return max(1, len(text) // 2)  # 保守估算

        while len(self.history) > 2:  # 至少保留 system + 最近1条
            total = sum(est_tokens(m.get("content", "") or "") for m in self.history)
            if total <= max_tokens:
                break
            # 删掉最早的一条非 system 消息
            for i, m in enumerate(self.history):
                if m["role"] != "system":
                    self.history.pop(i)
                    break
        self.tracer.log(f"上下文已精简（预算 {max_tokens} tokens）")

    # ---- 主循环 ----
    def run(self, user_input: str, max_steps=8, max_tokens: int = 6000):
        """处理一轮用户输入，返回最终回复，并记录轨迹。

        若配置了长期记忆（self.memory）：
          - 提问前：检索相关历史记忆，注入系统提示。
          - 回答后：把用户输入、回答写入记忆（重要信息）。
        """
        self.tracer = Tracer()  # 每轮一个新的追踪器

        # 【长期记忆】提问前：检索相关记忆并注入
        memory_context = ""
        if self.memory:
            recalls = self.memory.search(user_input)
            if recalls:
                from agent.memory import format_context
                memory_context = format_context(recalls)
                self.tracer.log(f"检索到 {len(recalls)} 条相关记忆")

        self.history.append({"role": "user", "content": user_input})
        print(f"\n🧑 用户：{user_input}")
        start_all = time.time()

        # 动态构造发给模型的 messages：原始 system + 记忆注入 + 对话历史。
        # 不在 history[0] 上改，避免记忆残留污染后续轮次。
        messages = [{"role": "system", "content": self._base_system}]
        if memory_context:
            messages[0]["content"] += "\n\n" + memory_context
        messages.extend(self.history[1:])  # history[0] 是原始 system，跳过

        for _ in range(max_steps):
            # 【修复】每轮都重新构建 messages，保证模型能看到最新历史（含上一步工具结果）
            # 之前 messages 在循环外只构建了一次，导致模型每轮看到的上下文相同，
            # 看不到工具已返回，于是反复调用同一工具。
            messages = [{"role": "system", "content": self._base_system}]
            if memory_context:
                messages[0]["content"] += "\n\n" + memory_context
            messages.extend(self.history[1:])  # history[0] 是原始 system，跳过

            # 发送前先控制上下文长度
            self.trim_history(max_tokens)

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=self.tools_spec,
                tool_choice="auto",
                temperature=0.3,
            )
            # 记录 token 用量
            u = response.usage
            if u:
                self.usage["prompt_tokens"] += u.prompt_tokens
                self.usage["completion_tokens"] += u.completion_tokens
                self.usage["total_tokens"] += u.total_tokens

            msg = response.choices[0].message

            # 情况 A：模型没有调用工具 -> 给出最终回答
            if not msg.tool_calls:
                self.history.append({"role": "assistant", "content": msg.content})
                self.tracer.add(type="answer", detail=msg.content,
                                duration_ms=round((time.time() - start_all) * 1000, 1))
                print(f"🤖 助手：{msg.content}")
                # 【长期记忆】回答后：把本轮对话沉淀为记忆（重要信息）
                if self.memory:
                    self.memory.add(f"用户问：{user_input}", meta={"type": "user", "time": time.time()})
                    self.memory.add(f"助手答：{msg.content}", meta={"type": "assistant", "time": time.time()})
                return msg.content

            # 情况 B：模型要调用工具
            tool_calls_spec = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
            self.history.append({
                "role": "assistant",
                "content": msg.content or "",  # 【修复】防止 content=null 干扰模型
                "tool_calls": tool_calls_spec,
            })

            # 执行工具，把结果回填，并记录到轨迹
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                fn = self.tool_registry.get(name)
                t0 = time.time()
                if fn is None:
                    result = f"❌ 未找到工具: {name}"
                else:
                    result = fn(**args)
                took_ms = round((time.time() - t0) * 1000, 1)
                print(f"🛠️  调用 {name}({args}) -> {result}")
                self.tracer.add(type="tool_call", detail=f"调用 {name}", tool=name,
                                args=args, duration_ms=took_ms)
                self.tracer.add(type="tool_result", detail=f"{name} 返回", tool=name,
                                result=result)
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        print("⚠️ 达到最大循环次数，强制结束。")
        return "已超过最大处理轮数。"

    def print_trace(self):
        """打印本轮运行轨迹。"""
        print(self.tracer.show())

    def print_usage(self):
        """打印 token 用量。"""
        u = self.usage
        print(f"📊 用量：输入 {u['prompt_tokens']} 输出 {u['completion_tokens']} "
              f"总计 {u['total_tokens']} tokens")
