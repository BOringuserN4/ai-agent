# -*- coding: utf-8 -*-
"""
agent/judge.py — LLM-as-Judge 自动评分器（2026/09/10）

思路：
  用「裁判 LLM」给「被测 Agent 的回答」打分。
  - 相比字符串精确匹配，LLM 能容忍自然语言表述的多样性。
  - 打分必须有**统一维度**，否则不同题目的分数不可比。

评分维度（4 个计权，各 0-5 分）：
  1. correctness       （正确性）：事实/结论对不对
  2. relevance         （切题性）：答的是不是用户问的那个问题
  3. no_hallucination  （不编造）：有没有超出证据/能力下结论（专抓 e5 那类）
  4. conciseness       （简洁度）：有没有绕弯子、废话

红线（不计权，一票否决）：
  compliance（合规）：是否文明礼貌、符合公序良俗。
  题目集里几乎不会不合格，所以它**不产生区分度**——因此不参与加权，
  只做「一旦违反直接判 fail」的否决项。

必达项（must_have，又一道否决）：
  有些要求不是「打多少分」而是「必须有」。如 e6「两个都要」漏一半，
  若只靠加权总分（80 分）会被 60 分及格线放行——这是评测失效的典型漏洞。
  所以 judge 额外接收 must_have 列表，逐项判断 true/false；**任一项不满足 → 直接 fail**，
  不看总分。这是继「合规」之后的第二道否决项。

重要设计原则（评测工程第一原则）：
  **能测量的东西，永远不要让 LLM 去判断。**
  - 耗时（elapsed_ms）、token 数、成本 → 由程序（runner）直接量；
  - 切不切题、编没编造 → 才交给 LLM 判。
  所以本文件**不评分耗时**，耗时由 eval_runner.py 测量并单列。

工程要点：
  - 强制裁判输出**严格 JSON**，便于程序解析（复用 json_mode.py（2026/09/08）思路）。
  - 裁判自身也可能出错 —— 解析失败要显式标记 error，**不能糊弄成 0 分**。
  - 温度调低（0），减少裁判打分抖动。
"""
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def is_env_error(e: BaseException) -> bool:
    """判断异常是不是「环境级」故障（网络/认证/超时）。

    评测里的异常分两种，处理方式完全不同：
      - 环境级（API key 失效 / 连不上 / 超时）→ 后续题目也会挂，应中断整轮
      - 普通异常（答案怪、解析失败）→ 属于「被测表现」，应记录后继续
    这里只负责识别环境级，供 eval_runner 决定是否中断。
    """
    try:
        import openai
        if isinstance(e, (openai.APIConnectionError, openai.AuthenticationError,
                          openai.PermissionDeniedError, openai.APITimeoutError)):
            return True
    except Exception:
        pass
    msg = str(e).lower()
    return any(k in msg for k in (
        "connection", "timed out", "timeout", "authentication",
        "api key", "unauthorized", "connection refused", "max retries",
    ))

# 4 个计权维度（各 25 分，合计 100）
DIMENSIONS = ["correctness", "relevance", "no_hallucination", "conciseness"]

_JUDGE_SYSTEM = (
    "你是一位严格的 AI 回答质量评审员（LLM-as-Judge）。"
    "你会拿到：用户问题、参考答案（含要点）、被测助手的回答。\n"
    "请从四个维度各给 0-5 的整数分：\n"
    "  correctness（正确性）、relevance（切题性）、"
    "no_hallucination（不编造，5=完全没有凭空下结论/编造数据）、"
    "conciseness（简洁度，5=不啰嗦不绕弯）。\n"
    "另外给出 compliance（合规性，true/false）：是否符合公序良俗、无有害内容。\n"
    "若我还提供了【必达项】列表，请逐项判断是否满足，输出 must_have 布尔数组，"
    "顺序与【必达项】一致；未提供则 must_have 输出 []。\n"
    "注意：只要关键事实与参考答案一致即可，不要求措辞相同。\n"
    "只输出一个 JSON，不要任何多余文字，格式严格如下：\n"
    '{"scores": {"correctness": 0-5, "relevance": 0-5, '
    '"no_hallucination": 0-5, "conciseness": 0-5}, '
    '"compliance": true, "must_have": [true, false], "reason": "一句话中文理由"}'
)


class Judge:
    def __init__(self, model="deepseek-chat"):
        key = os.getenv("DEEPSEEK_API_KEY", "")
        if not key or len(key) < 10:
            raise SystemExit("❌ 请先配置 .env 里的 DEEPSEEK_API_KEY")
        self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        self.model = model

    def score(self, question: str, expected: str, checks, answer: str, must_have=None) -> dict:
        """给一条回答打分（不含耗时，耗时由 runner 测）。

        Args:
            must_have: 必达项列表（可空）。任一项不满足 → pass=False，不看总分。

        Returns:
            dict: {
                "scores": {维度: 0-5},
                "total": 0-100,            # 4 维度加权总分
                "compliance": bool,        # 红线是否通过
                "must_have_met": [bool],   # 各必达项是否满足
                "pass": bool,              # 总分及格 且 合规 且 必达项全满足
                "reason": str,
                "error": str | None,       # 裁判解析失败时的错误信息
            }
        """
        must_have = must_have or []
        checks_text = "；".join(checks) if checks else "（无额外要点）"
        user_msg = (
            f"【用户问题】{question}\n"
            f"【参考答案】{expected}\n"
            f"【需覆盖的要点】{checks_text}\n"
        )
        if must_have:
            items = "\n".join(f"  {i+1}. {m}" for i, m in enumerate(must_have))
            user_msg += f"【必达项】（逐项判断 true/false，缺一项即不合格）\n{items}\n"
        user_msg += f"【被测助手的回答】{answer}\n\n请按系统要求只输出 JSON。"
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,  # 裁判要稳定，不要发挥
            )
            raw = resp.choices[0].message.content or ""
            data = self._parse_json(raw)
            scores = data.get("scores", {})
            # 规整：缺的维度按 0，超范围的截断到 0-5
            clean = {}
            for d in DIMENSIONS:
                v = scores.get(d, 0)
                try:
                    v = int(round(float(v)))
                except Exception:
                    v = 0
                clean[d] = max(0, min(5, v))
            total = round(sum(clean.values()) / (len(DIMENSIONS) * 5) * 100, 1)
            compliance = bool(data.get("compliance", True))
            # 必达项：逐项核验；数量不符或缺项按「未满足」保守处理
            raw_mh = data.get("must_have", []) or []
            if not isinstance(raw_mh, list):
                raw_mh = []
            must_have_met = [bool(v) for v in raw_mh[:len(must_have)]]
            while len(must_have_met) < len(must_have):
                must_have_met.append(False)  # 裁判漏答的项 → 视为未满足（保守）
            must_ok = all(must_have_met) if must_have else True
            return {
                "scores": clean,
                "total": total,
                "compliance": compliance,
                "must_have_met": must_have_met,
                # 三重门槛：及格线 60 + 合规红线 + 必达项全满足
                "pass": (total >= 60) and compliance and must_ok,
                "reason": data.get("reason", ""),
                "error": None,
                "env_error": False,
            }
        except Exception as e:
            # 裁判自身失败：显式标记 error，统计时单列，不糊弄成 0 分。
            # 再区分是否环境级故障，供 runner 决定是否中断整轮。
            return {
                "scores": {d: 0 for d in DIMENSIONS},
                "total": None,
                "compliance": None,
                "must_have_met": [False] * len(must_have),
                "pass": None,
                "reason": "",
                "error": f"{type(e).__name__}: {e}",
                "env_error": is_env_error(e),
            }

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """从裁判输出里抠出 JSON（容忍 ```json 代码块围栏和前后杂字）。"""
        text = raw.strip()
        if "```" in text:  # 去掉 markdown 代码块围栏
            text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError(f"裁判输出无 JSON：{raw[:120]}")
        return json.loads(text[start:end])


if __name__ == "__main__":
    # 自检：三条对照，验证「不编造」维度是否真的能抓出 e5 那类问题
    j = Judge()
    print("① 正常正确回答：")
    print(json.dumps(j.score(
        question="帮我算 123 * 456", expected="56088",
        checks=["结果为 56088"], answer="123 乘以 456 等于 56088。",
    ), ensure_ascii=False, indent=2))

    print("\n② 事实正确但越界下结论（e5 那类，应被 no_hallucination 扣分）：")
    print(json.dumps(j.score(
        question="上海和北京比，哪个更宜居？",
        expected="不能只凭天气下『哪更宜居』结论，需说明还需其它维度或无法判定",
        checks=["没有编造宜居结论", "说明了局限"],
        answer="上海现在 26°C，北京 18°C。所以上海比北京更宜居。",
    ), ensure_ascii=False, indent=2))

    print("\n③ 工具报错如实转达（e1 那类，应得高分）：")
    print(json.dumps(j.score(
        question="帮我算一下 100 / 0", expected="说明除数不能为 0",
        checks=["识别出除以零不合法", "没有编造结果"],
        answer="除以 0 是无意义的运算，计算器无法给出结果。",
    ), ensure_ascii=False, indent=2))
