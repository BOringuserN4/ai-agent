# -*- coding: utf-8 -*-
"""
agent/json_mode.py — 结构化 JSON 输出（教学模块）

核心思路：
  - 自然语言输出给人看，JSON 输出给代码用。
  - 结构化输出是 Agent 的「机器接口」——下游程序、Pipeline、Evaluator-Critic 都靠它。
  - OpenAI 兼容 API 用 `response_format={"type": "json_object"}` 让模型严格返回 JSON。
  - 具体字段约束写在 system prompt 里（schema-as-prompt）。

教学价值：
  - 把「LLM 决策 = 结构化输出」从 extractor 扩展到主对话。
  - 是后续 Pipeline / Evaluator-Critic / Fan-out 的基础设施。
  - temperature=0 在结构化输出场景的意义：决策类任务要稳定可复现。

设计取舍：
  - schema 字段约束放在 prompt 里（不是 tools/function calling），保持最小侵入。
  - 用户主动用 `/json <schema_name>` 触发，不污染默认对话。
  - 容错：解析失败时打印原文 + 标记，不抛异常（避免教学 demo 卡住）。
"""
import json
import time
from agent.tracing import Tracer

# 教学用的几个内置 schema。可扩展。
# 注意：JSON Schema 字段约束写在 prompt 里，模型据此输出。
JSON_SCHEMAS = {
    "math": {
        "description": "数学问题的结构化回答",
        "schema": {
            "answer": "数字或数学表达式（最终答案）",
            "explanation": "解题步骤的中文解释",
            "confidence": "0.0-1.0 之间的数字（模型对自己答案的把握）",
        },
        "instruction": (
            "请用严格的 JSON 回答（不要 Markdown 代码块标记，不要任何额外文字）。"
            "字段:\n"
            '- "answer": 数字或数学表达式（最终答案）\n'
            '- "explanation": 解题步骤的中文解释\n'
            '- "confidence": 0.0-1.0 之间的数字（你对答案的把握）\n'
            '示例：{"answer": 42, "explanation": "六乘以七", "confidence": 0.99}'
        ),
    },
    "weather": {
        "description": "天气查询的结构化回答",
        "schema": {
            "city": "城市名",
            "temperature": "温度数字（摄氏度）",
            "condition": "天气描述（如'晴朗'）",
            "advice": "出行建议",
        },
        "instruction": (
            "请用严格的 JSON 回答。字段:\n"
            '- "city": 城市名\n'
            '- "temperature": 温度数字（摄氏度）\n'
            '- "condition": 天气描述\n'
            '- "advice": 出行建议\n'
            '示例：{"city": "北京", "temperature": 23, "condition": "晴朗", "advice": "适合外出"}'
        ),
    },
    "summary": {
        "description": "文本摘要的结构化回答",
        "schema": {
            "one_liner": "一句话总结（≤ 30 字）",
            "key_points": "数组：3-5 个关键要点",
            "category": "文本类别（如'技术'/'新闻'/'故事'）",
        },
        "instruction": (
            "请用严格的 JSON 回答。字段:\n"
            '- "one_liner": 一句话总结（≤ 30 字）\n'
            '- "key_points": 数组，3-5 个关键要点\n'
            '- "category": 文本类别\n'
            '示例：{"one_liner": "示例摘要", "key_points": ["点1","点2"], "category": "技术"}'
        ),
    },
}


def list_schemas() -> list:
    """返回可用的 schema 列表（描述）。"""
    return [(name, info["description"]) for name, info in JSON_SCHEMAS.items()]


def get_schema_instruction(name: str) -> str:
    """取指定 schema 的字段约束文本（注入到 system prompt）。"""
    if name not in JSON_SCHEMAS:
        available = ", ".join(JSON_SCHEMAS.keys())
        raise ValueError(f"未知 schema: {name}。可选: {available}")
    return JSON_SCHEMAS[name]["instruction"]


def parse_json_strict(content: str) -> dict:
    """容错解析 JSON 字符串。

    Returns:
        dict: 解析成功返回字段 dict；失败返回 {"_parse_error": True, "_raw": 原文}
    """
    if not content:
        return {"_parse_error": True, "_raw": content}
    # 直接尝试
    try:
        return json.loads(content)
    except Exception:
        pass
    # 容错：找第一个 { 到最后一个 } 之间的子串
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except Exception:
            pass
    return {"_parse_error": True, "_raw": content}


def run_json_mode(agent, user_input: str, schema_name: str, max_steps=8) -> dict:
    """以 JSON 模式跑一轮对话。

    Args:
        agent: Agent 实例（已初始化，含 client / history / tracer / usage）。
        user_input: 用户问题。
        schema_name: 预定义 schema 名（如 "math" / "weather" / "summary"）。

    Returns:
        dict: 解析后的 JSON 对象。如果模型调了工具，结果会自动拼接回 JSON。
    """
    if schema_name not in JSON_SCHEMAS:
        raise ValueError(f"未知 schema: {schema_name}。可选: {list(JSON_SCHEMAS.keys())}")

    schema_instr = get_schema_instruction(schema_name)
    # 【修复】用临时 Agent（隔离 router 的 system prompt 干扰）
    from agent.core import Agent
    base_system = "你是一个乐于助人的助手。"
    json_agent = Agent(
        system_prompt=base_system,
        tools=None,  # 用全部工具
        memory=None,  # JSON 模式不走长期记忆
    )
    json_agent.client = agent.client  # 复用同一个 LLM client
    json_agent.tracer = Tracer()

    extended_system = base_system + "\n\n" + schema_instr
    json_agent.history = [{"role": "system", "content": extended_system},
                           {"role": "user", "content": user_input}]
    # 把 json_agent 的 tracer 也设为 agent.tracer（方便统一打印）
    # 直接用 agent.tracer 记录步骤
    agent.tracer = Tracer()

    print(f"\n🧑 用户：{user_input}\n📐 JSON 模式（schema={schema_name}）")
    start_all = time.time()

    for _ in range(max_steps):
        # 【修复】messages 每轮重建（避免重复调用工具 bug）
        messages = [{"role": "system", "content": extended_system}]
        messages.extend(json_agent.history[1:])

        agent.trim_history()
        try:
            response = json_agent.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=json_agent.tools_spec,
                tool_choice="auto",
                temperature=0,  # 结构化输出用 0 保证稳定
                response_format={"type": "json_object"},  # 强制 JSON
            )
        except Exception as e:
            # 极少数 API 不支持 response_format 时降级
            if "response_format" in str(e):
                response = json_agent.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    tools=json_agent.tools_spec,
                    tool_choice="auto",
                    temperature=0,
                )
            else:
                raise

        u = response.usage
        if u:
            json_agent.usage["prompt_tokens"] += u.prompt_tokens
            json_agent.usage["completion_tokens"] += u.completion_tokens
            json_agent.usage["total_tokens"] += u.total_tokens

        msg = response.choices[0].message

        # 无工具调用：直接拿 JSON 结果
        if not msg.tool_calls:
            parsed = parse_json_strict(msg.content or "")
            json_agent.history.append({"role": "assistant", "content": msg.content or "{}"})
            json_agent.tracer.add(type="json_answer", detail=str(parsed),
                             duration_ms=round((time.time() - start_all) * 1000, 1))
            print(f"🤖 助手(JSON)：{parsed}")
            # 同时把 token 用量同步给传入的 router（让 /usage 能看到）
            agent.usage["prompt_tokens"] += json_agent.usage["prompt_tokens"]
            agent.usage["completion_tokens"] += json_agent.usage["completion_tokens"]
            agent.usage["total_tokens"] += json_agent.usage["total_tokens"]
            return parsed

        # 模型想调工具：执行并回填（与 core.py 主循环一致）
        tool_calls_spec = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
        json_agent.history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": tool_calls_spec,
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            fn = json_agent.tool_registry.get(name)
            t0 = time.time()
            if fn is None:
                result = f"❌ 未找到工具: {name}"
            else:
                result = fn(**args)
            took_ms = round((time.time() - t0) * 1000, 1)
            print(f"🛠️  调用 {name}({args}) → {result}")
            json_agent.tracer.add(type="tool_call", detail=f"调用 {name}", tool=name,
                             args=args, duration_ms=took_ms)
            json_agent.tracer.add(type="tool_result", detail=f"{name} 返回", tool=name,
                             result=result)
            json_agent.history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    print("⚠️ 达到最大循环次数，强制结束。")
    return {"_error": "max_steps_reached", "_raw": json_agent.history[-1].get("content", "")}