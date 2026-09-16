# -*- coding: utf-8 -*-
"""
agent/evaluator_critic.py — Evaluator-Critic 模式（生成 → 批判 → 重做）

结构定位（2026/09/16）：
  - 谁控制流：**代码**（固定「生成 → 评分 → 不达标重做」的循环，轮次由代码封顶）
  - 信息流：**串联 + 回环**（批判意见回流给生成者，形成闭环）
  - 与前面模式的差别：这是第一个「**监督关系**」——一个角色管另一个角色的质量，
    而不是 Router 那种平级「分工」。

为什么要单独一个批判者（对应判据③「不同视角」）：
  让生成者自己批自己（self-critique）会撞上「**自我确认偏差**」——它刚做完推理，
  满脑子都是自己这么选的理由；再让它挑错，它倾向于**辩护**而不是找漏洞。
  所以批判者必须是**另一个立场**：职责就是找茬，找不出毛病算失职。

  注意：关键是「立场独立」，**不是「必须两个 Agent 实体」**。
  同一 Agent 换一套批判人格 + 清掉生成时的上下文，也算独立立场（省一半钱）；
  但「同一个 Agent 原地加一句『你再检查一遍』」不算，那还是自我确认偏差。

该用 / 不该用（四条否决线，踩任意一条就别做）：
  ✗ 有客观可程序验证的标准（能跑测试、能算）→ 用代码验证，别雇 LLM 评委
  ✗ 评判标准说不清（如「够不够有感染力」）→ 打分漂移，重做没有方向
  ✗ 任务便宜、单次就够 → 多一轮「评 + 重做」≈ 多付一份生成的钱
  ✗ 无法从批判中改进（缺的是信息，不是做得好不好）→ 批十遍也变不出新信息

设计要点：
  - **阈值由代码定**（人的决策），批判者只负责给分；
    不让裁判自己宣布「及格」，否则评分漂移会直接变成放行标准漂移。
  - 轮次由代码封顶；封顶后输出「当前最好的一版」并**显式标注未达标**。
  - 批判者只看「任务 + 答案」，**看不到生成者的推理过程**（立场不被带偏）。
  - 每轮都上报 Langfuse（能看到「第几轮、几分」），token 按角色归因。
"""
import contextlib
import json
import time

from agent.core import Agent, get_langfuse
from agent.json_mode import parse_json_strict

# 批判者必须返回的字段（schema-as-prompt，沿用本项目的结构化输出传统）
CRITIC_INSTRUCTION = (
    "请用严格的 JSON 回答（不要 Markdown 代码块标记，不要任何额外文字）。字段:\n"
    '- "rule_ok": 布尔，是否**逐条**满足任务里列出的硬性要求（有一条没满足就是 false）\n'
    '- "rule_issues": 数组，逐条列出**具体违反**的硬性要求（没有则 []）\n'
    '- "craft": 对象，给出 3 个「手艺分」，各 0-10 的整数：\n'
    '    "scenario": 卖点是否与具体使用场景绑定（越具体越高）\n'
    '    "differentiation": 是否有区别于同类的记忆点（越不套话越高）\n'
    '    "rhythm": 读起来节奏与语感（越顺越高）\n'
    '- "fix": 一句话说明下一版最该改什么\n'
    '示例：{"rule_ok": false, "rule_issues": ["字数 145 字，超出 120 字上限"], '
    '"craft": {"scenario": 3, "differentiation": 4, "rhythm": 6}, '
    '"fix": "压缩到 120 字以内，并把降噪卖点绑定到通勤场景"}\n'
    "注意：手艺分**不要**轻易给 9-10 分。只有真正具体、不套话、读起来顺的才算 8 分以上；"
    "泛泛而谈、堆形容词的一律 5 分以下。"
)

# 批判者人格：与生成者天生冲突——生成者想「写漂亮」，批判者只想「挑出毛病」
CRITIC_SYSTEM = (
    "你是一位极其严格的内容评审员。你要做两件事：\n"
    "① **合规核对**：对照任务里的每一条硬性要求，逐条核对答案是否满足；\n"
    "② **手艺评分**：合规之外，给「场景绑定 / 差异化 / 语感节奏」三项各 0-10 分。\n"
    "你不负责夸奖，也不负责替作者找理由——找不出问题就是你的失职。\n"
    "手艺分从严：堆形容词、说套话、卖点不与具体场景挂钩的，一律 5 分以下；"
    "只有真正具体、有记忆点、读起来顺口的才给 8 分以上。"
)

# 生成者人格：只管写得好看、达标
GENERATOR_SYSTEM = (
    "你是一位中文文案写手。请严格按任务里的每一条硬性要求写作，"
    "写完后自己核对一遍字数与禁用词。只输出文案正文，不要解释、不要标题、不要加引号。"
)


def _call_json(agent, prompt: str, instruction: str, span_name: str):
    """单次结构化 JSON 调用（不走 ReAct 循环，直接要 JSON）。

    为什么不复用 json_mode.run_json_mode：那个函数会用「你是一个乐于助人的助手」
    **覆盖**传入 Agent 的 system prompt，而批判者的人格正是它的立场来源，不能被覆盖。

    Returns:
        (parsed_dict, usage_dict)
    """
    lf = get_langfuse()
    messages = [
        {"role": "system", "content": agent._base_system + "\n\n" + instruction},
        {"role": "user", "content": prompt},
    ]
    ctx = (
        lf.start_as_current_observation(
            name=span_name, as_type="generation", model="deepseek-flash",
            input={"task": prompt[:300]},
        )
        if lf else contextlib.nullcontext()
    )
    with ctx as span:
        started = time.time()
        try:
            resp = agent.client.chat.completions.create(
                model="deepseek-flash",
                messages=messages,
                temperature=0,              # 评审要稳，不要发挥
                response_format={"type": "json_object"},
            )
        except Exception as e:
            # 少数兼容端点不支持 response_format 时降级
            if "response_format" in str(e):
                resp = agent.client.chat.completions.create(
                    model="deepseek-flash", messages=messages, temperature=0,
                )
            else:
                if span is not None:
                    span.update(level="ERROR", status_message=f"{type(e).__name__}: {e}")
                raise
        u = resp.usage
        usage = {
            "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
            "total_tokens": getattr(u, "total_tokens", 0) or 0,
        }
        parsed = parse_json_strict(resp.choices[0].message.content or "")
        if span is not None:
            span.update(
                output=parsed,
                usage_details={"input": usage["prompt_tokens"],
                               "output": usage["completion_tokens"],
                               "total": usage["total_tokens"]},
                metadata={"elapsed_ms": round((time.time() - started) * 1000, 1)},
            )
    return parsed, usage


class EvaluatorCritic:
    """Evaluator-Critic：生成 → 批判 → 不达标重做 → 封顶输出。"""

    def __init__(self, threshold: int = 85, max_rounds: int = 3):
        """
        Args:
            threshold: 及格线（0-100）。**由代码定**，是人的决策，不是裁判的自我评价。
            max_rounds: 最多生成几版（含第一版）。封顶后输出当前最好的一版。
        """
        self.threshold = threshold
        self.max_rounds = max_rounds
        # 两个独立 Agent：立场分离是本模式的立身之本
        self.generator = Agent(system_prompt=GENERATOR_SYSTEM, tools=None)
        self.critic = Agent(system_prompt=CRITIC_SYSTEM, tools=None)
        self.usage = {"generator": 0, "critic": 0, "total": 0}

    # ---- 生成 / 重做 ----
    def _generate(self, task: str, round_no: int) -> str:
        self.generator.reset()
        return self.generator.run_traced(
            task, trace_name=f"ec-generate-r{round_no}", user_id="demo",
        )

    def _revise(self, task: str, prev_answer: str, critique: dict, round_no: int) -> str:
        """带着批判意见重做——这就是回环：批判结果回流给生成者。"""
        issues = "；".join(critique.get("rule_issues") or []) or "（无）"
        craft = critique.get("craft") or {}
        craft_str = "，".join(
            f"{k}={craft.get(k, '-')}/10" for k in self.CRAFT_DIMS
        ) or "（无）"
        prompt = (
            f"【原始任务】\n{task}\n\n"
            f"【上一版文案】\n{prev_answer}\n\n"
            f"【评审意见】得分 {critique.get('score')}\n"
            f"  硬性要求违反：{issues}\n"
            f"  手艺分：{craft_str}\n"
            f"【修改建议】{critique.get('fix', '')}\n\n"
            "请写一版新文案，**逐条解决上述问题**，其余要求保持不变。只输出文案正文。"
        )
        self.generator.reset()
        return self.generator.run_traced(
            prompt, trace_name=f"ec-revise-r{round_no}", user_id="demo",
        )

    # ---- 打分（代码定规则，裁判只提供事实）----
    CRAFT_DIMS = ("scenario", "differentiation", "rhythm")
    RULE_FAIL_CAP = 59      # 硬性要求不合规 = 一票否决，封顶 59
    CRAFT_BASE = 60         # 合规之后，剩下的 40 分由手艺分决定

    def _score(self, parsed: dict) -> int:
        """把裁判给的事实（rule_ok + craft 三维）折算成 0-100 的总分。

        为什么折算放在代码里：**阈值和加权都是人的决策**，
        裁判只负责提供「事实」（是否符合、各维度几分）。
        这样评分维度一改，全班题目的分数口径仍然一致、可比。
        """
        if not parsed.get("rule_ok"):
            return self.RULE_FAIL_CAP
        craft = parsed.get("craft") or {}
        got = sum(int(craft.get(d, 0) or 0) for d in self.CRAFT_DIMS)
        return self.CRAFT_BASE + round(got / 30 * (100 - self.CRAFT_BASE))

    # ---- 批判 ----
    def _critique(self, task: str, answer: str, round_no: int) -> dict:
        prompt = (
            f"【任务与硬性要求】\n{task}\n\n"
            f"【待评审的答案】\n{answer}\n\n"
            "请对照硬性要求逐条核对。注意：你只看到任务和答案，"
            "不需要猜测作者的想法，只看答案本身是否达标。"
        )
        parsed, usage = _call_json(
            self.critic, prompt, CRITIC_INSTRUCTION, span_name=f"ec-critique-r{round_no}",
        )
        self.usage["critic"] += usage["total_tokens"]
        self.usage["total"] += usage["total_tokens"]
        if parsed.get("_parse_error"):
            # 裁判解析失败要显式暴露，不能糊弄成 0 分
            parsed = {"rule_ok": False, "rule_issues": ["裁判输出解析失败"],
                      "craft": {}, "fix": "重试", "_parse_error": True}
        # 分数由代码折算（裁判只给事实）
        parsed["score"] = self._score(parsed)
        return parsed

    # ---- 主流程 ----
    def run(self, task: str, verbose: bool = True) -> dict:
        print(f"\n{'=' * 58}")
        print(f"⚖️  Evaluator-Critic 启动（及格线 {self.threshold}，最多 {self.max_rounds} 轮）")
        print(f"{'=' * 58}")
        print(f"📋 任务：{task[:120]}{'...' if len(task) > 120 else ''}")

        # 每次 run 都从零开始统计，避免同一实例跑两次时用量叠加
        self.generator.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.usage = {"generator": 0, "critic": 0, "total": 0}

        history = []          # 每轮记录：{round, score, answer, issues}
        best = None
        answer = ""

        for r in range(1, self.max_rounds + 1):
            if r == 1:
                if verbose:
                    print(f"\n--- 第 {r} 轮：生成 ---")
                answer = self._generate(task, r)
            else:
                if verbose:
                    print(f"\n--- 第 {r} 轮：带着批评重做 ---")
                answer = self._revise(task, answer, history[-1]["critique"], r)

            g_tokens = self.generator.usage["total_tokens"]
            self.usage["generator"] = g_tokens
            self.usage["total"] = g_tokens + self.usage["critic"]

            if verbose:
                print(f"✍️  第 {r} 版文案：{answer[:160]}{'...' if len(answer) > 160 else ''}")

            critique = self._critique(task, answer, r)
            score = critique.get("score", 0)
            history.append({"round": r, "score": score, "answer": answer,
                            "critique": critique})
            if verbose:
                issues = "；".join(critique.get("rule_issues") or []) or "（无）"
                craft = critique.get("craft") or {}
                craft_str = "，".join(
                    f"{k} {craft.get(k, '-')}/10" for k in self.CRAFT_DIMS
                )
                print(f"🧐 批判：{score} 分｜硬性违反：{issues}")
                print(f"   手艺分：{craft_str}")
                print(f"   建议：{critique.get('fix', '')}")

            if best is None or score > best["score"]:
                best = {"round": r, "score": score, "answer": answer}

            if score >= self.threshold:
                if verbose:
                    print(f"\n✅ 第 {r} 轮达标（{score} ≥ {self.threshold}），停止重做。")
                break
            if r == self.max_rounds and verbose:
                print(f"\n⚠️ 已到轮次上限仍未达标（{score} < {self.threshold}）。"
                      f"输出历史最好的一版（第 {best['round']} 轮，{best['score']} 分）。")

        # 结论块
        if verbose:
            print(f"\n{'─' * 58}")
            print("📊 轮次 × 得分（分数是测量值，决定是否停的是阈值）：")
            for h in history:
                flag = "✅ 达标" if h["score"] >= self.threshold else "✗ 未达标"
                print(f"   第 {h['round']} 轮：{h['score']:>3} 分  {flag}")
            print(f"💰 token 用量：生成者 {self.usage['generator']}"
                  f"｜批判者 {self.usage['critic']}"
                  f"｜合计 {self.usage['total']}")
            print(f"{'─' * 58}")

        return {
            "answer": best["answer"],
            "rounds": len(history),
            "final_score": history[-1]["score"],
            "best_score": best["score"],
            "passed": history[-1]["score"] >= self.threshold,
            "history": history,
            "usage": dict(self.usage),
        }


# ============ 两个内置演示任务（教学用，一正一反）============

# 正例：能挑出错、且挑错之后改得动
POSITIVE_TASK = (
    "为「星野」降噪耳机写一条电商主图文案。硬性要求（共 9 条，逐条核对）：\n"
    "① 正好 36 个字（含标点）；② 必须含「降噪」；③ 必须含「12 小时」；\n"
    "④ 必须含「180 克」；⑤ 不得出现数字以外的阿拉伯符号；\n"
    "⑥ 不得使用：最、第、绝、完美、极致；⑦ 不得使用感叹号；\n"
    "⑧ 必须以「星野」开头；⑨ 只输出文案本身。\n"
    "（合规只是及格线，还要写得有场景、有记忆点、读得顺。）"
)

# 反例：命中否决线④「无法从批判中改进」——缺的是信息，不是做得好不好
NEGATIVE_TASK = (
    "请逐字复述《星际联邦员工手册》第 7 条原文，一字不差。\n"
    "（说明：这份手册没有提供给你，你也没有任何可以查阅它的工具。）"
)


def main():
    ec = EvaluatorCritic(threshold=85, max_rounds=3)
    print("🧪 正例演示：约束明确、可挑错、可改好")
    ec.run(POSITIVE_TASK)


if __name__ == "__main__":
    main()
