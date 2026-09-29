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
  "questions": ["问法1", "问法2"],  // 用户日后**可能怎么问**这条信息，2~4 条
  "tags": ["preference", "fact"] // 类别标签
}

questions 的写法要求（重要）：
  - 写**用户视角的口语化问句**，覆盖不同措辞，而不是复述 text；
  - 要**通用**，不要只写某一种固定说法（避免只能匹配特定问法）；
  - 例：text「用户是一名测试开发工程师」→ questions
        ["我是做什么工作的", "我的职业是什么", "我干啥的"]

判断标准（按优先级，只保留前三档）：
1. 用户的明确偏好/个人信息（姓名、职业、习惯、口味）
2. 跨会话有用的具体事实（项目阶段、关键决策、技术偏好）
3. 不要记的：问候、寒暄、"你好""谢谢"、一次性数学计算、模糊回复("嗯""哦")"""


QUESTIONS_PROMPT = """你是「记忆检索助手」。给定一条已记住的事实，写出用户日后**可能怎么问**它。

要求：
- 输出严格的 JSON，格式 {"questions": ["问法1", "问法2", "问法3"]}
- 2~4 条，覆盖不同措辞（正式/口语/间接），不要只换标点
- 必须让这些问题**只能由这条事实回答**（不要写成能泛化到别的事实的问法）
- 用用户第一人称视角问（「我…」）

例：事实「用户是一名测试开发工程师」
     → {"questions": ["我是做什么工作的", "我的职业是什么", "我干啥的"]}"""


def suggest_questions(text: str, client=None, model: str = "deepseek-flash",
                      reasoning_effort: str = "none") -> list:
    """给一条**已存在的**记忆补出「可能被怎么问」。

    用途：迁移旧记忆（早期存入的记忆没有 questions，享受不到增富收益）。
    返回问题列表；失败时返回空列表（调用方应容忍）。
    """
    import json as _json
    import os as _os
    text = (text or "").strip()
    if not text:
        return []
    try:
        if client is None:
            from openai import OpenAI
            key = _os.getenv("DEEPSEEK_API_KEY", "")
            if not key:
                return []
            client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        # ⚠️ 必须关思考（2026/09/29 实测）：deepseek-flash 默认开思考，
        # 生成 4 条问题会烧光 max_tokens 预算 → content 为空、finish_reason=length
        # → 静默返回 []。这与 2026/09/19 在本地模型上踩的坑**同一类**：
        # 思考吃光输出预算导致的**静默失败**。
        kwargs = dict(
            model=model, temperature=0,
            messages=[{"role": "system", "content": QUESTIONS_PROMPT},
                      {"role": "user", "content": f"事实：{text}"}],
            max_tokens=400,
        )
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        resp = client.chat.completions.create(**kwargs)
        content = (resp.choices[0].message.content or "").strip()
        data = _json.loads(content[content.find("{"):content.rfind("}") + 1])
        qs = data.get("questions") or []
        return [str(q).strip() for q in qs if str(q).strip()][:4]
    except Exception:
        return []


def build_embed_text(text: str, questions: list = None) -> str:
    """把「事实 + 可能被怎么问」拼成**专用于向量化**的文本。

    为什么要拼（2026/09/29 实测）：
      检索质量取决于「记忆向量」与「问句向量」的距离。把记忆改写成
      「事实 + 可回答的问法」，能显著拉高该召回组的相似度，
      且**不抬高无关记忆的分数**（不引入误召）。

    为什么单独一个函数：
      ① 它是**纯函数**，可单独测、可 A/B（改拼法不用动抽取器）；
      ② 与「注入上下文的文本」解耦 —— 注入仍用精简 text，省 token。

    实测（docs/memory-recall-fix.md）：命中的问法相似度上升约 +0.10~0.20，
    无关问法保持在阈值以下。
    """
    text = (text or "").strip()
    if not questions:
        return text
    qs = [q.strip() for q in questions if q and q.strip()]
    if not qs:
        return text
    # 去掉 text 末尾的句号类标点，避免拼出「。。」
    text = text.rstrip("。.！!？?；;，,、 ")
    return f"{text}。可能被问及：{'；'.join(qs[:4])}"


class MemoryExtractor:
    """让 LLM 决定"这轮对话是否值得长期记"的过滤器。"""

    def __init__(self, model="deepseek-flash", client=None, reasoning_effort=None,
                 max_tokens=600):
        """
        Args:
            model: 模型名。
            client: 可选的 OpenAI 兼容客户端（本地模型/自定义端点时传入）。
            reasoning_effort: 传给模型（None=不传）。**本地小模型强烈建议设 "none"**：
                实测 gemma4-e4b 在思考模式下会把 max_tokens 预算全烧在推理上，
                正文返回空字符串，导致抽取器兜底为 keep=False（等于「什么都不记」）。
            max_tokens: 输出上限。**思考模式会吃掉它** —— 默认 600 是为留足预算：
                实测该任务思考约用 9~49 token，但生成类任务（如 suggest_questions）
                可烧光 200 的上限，导致 content 为空、finish_reason=length，
                表现为**静默失败**（2026/09/29 实测踩到）。
        """
        self.model = model
        self.client = client  # 懒加载：调用时才建
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens

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
        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content":
                    f"用户说：{user_input}\n助手答：{assistant_reply}\n\n请判断是否值得长期记。"}
            ],
            temperature=0,
            max_tokens=self.max_tokens,
        )
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        try:
            resp = client.chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "").strip()
            # ⚠️ 显式识别「思考吃光输出预算」（2026/09/29）：
            # 这时 content 为空且 finish_reason=length。若不特判，会走到下面的
            # 解析失败分支，与「真的没什么可记」长得一样 → **静默失败**。
            if not content and resp.choices[0].finish_reason == "length":
                u = getattr(resp, "usage", None)
                detail = getattr(getattr(u, "completion_tokens_details", None),
                                 "reasoning_tokens", None)
                return {"keep": False, "text": "", "questions": [], "tags": [],
                        "_error": f"budget_exhausted:reasoning={detail}"}
        except Exception as e:
            # API 失败：兜底为不记（避免污染记忆库）
            return {"keep": False, "text": "", "questions": [], "tags": [],
                    "_error": f"api:{type(e).__name__}"}

        # 容错解析：找 JSON 子串
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start < 0 or end <= start:
                return {"keep": False, "text": "", "questions": [], "tags": [],
                        "_error": "no_json"}
            data = json.loads(content[start:end])
            # 注意：某些模型（如 NuExtract）在 keep=false 时把 text 置为 null，
            # str(None) 会得到字符串 "None" → 这里统一归一为空串。
            raw_text = data.get("text")
            raw_qs = data.get("questions")
            qs = []
            if isinstance(raw_qs, list):
                qs = [str(q).strip() for q in raw_qs if str(q).strip()]
            return {
                "keep": bool(data.get("keep", False)),
                "text": ("" if raw_text is None else str(raw_text)).strip(),
                "questions": qs[:4],
                "tags": data.get("tags", []) if isinstance(data.get("tags"), list) else [],
            }
        except Exception:
            return {"keep": False, "text": "", "questions": [], "tags": [],
                    "_error": "parse_failed"}