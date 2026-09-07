# -*- coding: utf-8 -*-
"""
agent/extractor.py — 记忆重要性过滤器（LLM 决策版）

核心思路：
  - 用户每轮对话产生大量文本，但并不是每条都值得长期记忆。
  - 让 LLM 自己判断"什么值得记"，比硬编码正则规则更聪明。
  - 模型只输出结构化 JSON：是否要记 + 一句话概括 + 类别标签。

设计要点：
  - 结构化输出（JSON）是 LLM 决策的标准模式，比正则灵活、比函数调用轻。
  - temperature=0：决策类任务用 0 让结果更稳定、可复现。
  - max_tokens=200：限制输出，避免模型啰嗦浪费 token。
  - 容错：模型偶尔不返回严格 JSON，用 try/except 兜底为 keep=False。

为什么不让 LLM 决定更好？
  - 涉及"语义理解"的判断（如"用户的偏好"），硬编码规则很难覆盖。
  - LLM 通过 prompt 直接理解判断标准，且能跨语境泛化。
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()


SYSTEM_PROMPT = """你是「记忆过滤器」。判断当前对话中是否有值得长期记住的信息。
只输出严格的 JSON（不要任何解释、不要 Markdown 代码块标记）：
{
  "keep": true/false,           // 是否值得长期记住
  "text": "一段话",             // keep=true 时用一句话概括要记住的事实
  "tags": ["preference", "fact"] // 类别标签
}

判断标准（按优先级，只保留前三档）：
1. 用户的明确偏好/个人信息（姓名、职业、习惯、口味）
2. 跨会话有用的具体事实（项目阶段、关键决策、技术偏好）
3. 不要记的：问候、寒暄、"你好""谢谢"、一次性数学计算、模糊回复("嗯""哦")"""


class MemoryExtractor:
    """让 LLM 决定"这轮对话是否值得长期记"的过滤器。"""

    def __init__(self, model="deepseek-chat", client=None):
        self.model = model
        self.client = client  # 懒加载：调用时才建

    def _ensure_client(self):
        if self.client is None:
            from openai import OpenAI
            key = os.getenv("DEEPSEEK_API_KEY", "")
            if not key or len(key) < 10:
                raise RuntimeError("❌ 请先配置 .env 里的 DEEPSEEK_API_KEY")
            self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        return self.client

    def extract(self, user_input: str, assistant_reply: str) -> dict:
        """让 LLM 判断这轮对话是否值得记。

        Returns:
            dict: {keep: bool, text: str, tags: list[str], _error?: str}
        """
        client = self._ensure_client()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content":
                        f"用户说：{user_input}\n助手答：{assistant_reply}\n\n请判断是否值得长期记。"}
                ],
                temperature=0,
                max_tokens=200,
            )
            content = resp.choices[0].message.content.strip()
        except Exception as e:
            # API 失败：兜底为不记（避免污染记忆库）
            return {"keep": False, "text": "", "tags": [], "_error": f"api:{type(e).__name__}"}

        # 容错解析：找 JSON 子串
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start < 0 or end <= start:
                return {"keep": False, "text": "", "tags": [], "_error": "no_json"}
            data = json.loads(content[start:end])
            return {
                "keep": bool(data.get("keep", False)),
                "text": str(data.get("text", "")).strip(),
                "tags": data.get("tags", []) if isinstance(data.get("tags"), list) else [],
            }
        except Exception:
            return {"keep": False, "text": "", "tags": [], "_error": "parse_failed"}