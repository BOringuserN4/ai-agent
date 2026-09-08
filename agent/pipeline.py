# -*- coding: utf-8 -*-
"""
agent/pipeline.py — Pipeline 模式（Agent 串联）

核心思路：
  - Pipeline = 把多个 Agent 串起来，上一步输出 = 下一步输入。
  - 中间状态是 dict（JSON 结构化），下游 Agent 可以直接拿字段。
  - 这是教材第3 节"10 种编排模式"中的第一种，地位关键。

教学价值：
  - 演示「为什么结构化输出是 multi-agent 的基础设施」
    ——下游 Agent 必须能"听懂"上游在说什么，dict 比字符串好。
  - 演示「状态传递」：state dict 在多 Agent 间流转。
  - 是后续 Evaluator-Critic / Fan-out / Debate 等模式的基础。

设计要点：
  - 每个 step 指定 agent 实例 + schema（结构化输出 schema）。
  - prompt 自动拼接：上一步输出 + 当前任务。
  - 完整 state 在每步追加，方便 debug 和 trace。
"""
import json
import time


# 下游 Agent 拿到的 prompt 模板（让 Agent 知道前一步发生了什么）
STEP_PROMPT_TEMPLATE = """【Pipeline 上一步输出】
{prev_output}

【本步任务】
{current_task}

请基于上一步的结构化输出，完成本步任务。
"""


class PipelineStep:
    """Pipeline 中的一个步骤。"""

    def __init__(self, name: str, agent, schema_name: str, task_instruction: str):
        """
        Args:
            name: 步骤名（如 'math' / 'summary'），用作 state 字典的 key。
            agent: Agent 实例（必须能调 run_json_mode）。
            schema_name: 此步骤的 JSON schema 名（如 'math' / 'summary'）。
            task_instruction: 给此步骤 Agent 的任务描述。
        """
        self.name = name
        self.agent = agent
        self.schema_name = schema_name
        self.task_instruction = task_instruction


class Pipeline:
    """Pipeline 模式——把多个 Agent 按顺序串起来。"""

    def __init__(self, name: str, steps: list):
        self.name = name
        self.steps = steps  # List[PipelineStep]

    def run(self, initial_input: str, initial_task: str = None) -> dict:
        """跑完整条 Pipeline。

        Args:
            initial_input: 第一个步骤的输入。
            initial_task: 第一个步骤的任务描述（None 时用 step.task_instruction）。

        Returns:
            dict: 完整 state，键是各 step.name，值是该步的结构化输出。
        """
        print(f"\n{'='*50}")
        print(f"🚀 Pipeline '{self.name}' 启动（{len(self.steps)} 步）")
        print(f"{'='*50}")

        state = {"_initial_input": initial_input}
        from agent.json_mode import run_json_mode

        for i, step in enumerate(self.steps):
            print(f"\n📍 步骤 {i+1}/{len(self.steps)}: {step.name} (schema={step.schema_name})")
            t0 = time.time()

            # 构造 prompt：把"上一步的 JSON 输出"喂给当前 Agent
            if i == 0:
                # 第一步：直接用 initial_input + task
                prev_summary = f"（初始输入）{initial_input}"
            else:
                prev_step = self.steps[i - 1]
                prev_output = state[prev_step.name]
                prev_summary = json.dumps(prev_output, ensure_ascii=False, indent=2)

            task = initial_task if (i == 0 and initial_task) else step.task_instruction
            prompt = STEP_PROMPT_TEMPLATE.format(
                prev_output=prev_summary,
                current_task=task,
            )

            # 跑这一步 Agent（JSON 模式）
            output = run_json_mode(step.agent, prompt, step.schema_name)
            state[step.name] = output
            print(f"  ✅ {step.name} 耗时 {time.time()-t0:.2f}s")

        print(f"\n{'='*50}")
        print(f"🏁 Pipeline 完成，state keys: {list(state.keys())}")
        print(f"{'='*50}\n")
        return state

    def last_output(self, state: dict) -> dict:
        """取最后一步的输出（方便展示）。"""
        return state[self.steps[-1].name] if self.steps else {}


# ============ 预定义 Pipeline 场景（教学用）============


def build_math_to_summary_pipeline(ma) -> Pipeline:
    """场景 1：数学计算 → 总结

    步骤：
      1. math agent: 算用户提的数学问题 → 输出 {answer, explanation, confidence}
      2. summary agent: 把计算结果写成一句话总结
    """
    from agent.json_mode import JSON_SCHEMAS
    math_agent = ma.experts.get("math") or ma.router
    summary_agent = ma.experts.get("general") or ma.router

    steps = [
        PipelineStep(
            name="math",
            agent=math_agent,
            schema_name="math",
            task_instruction=(
                "请用 math schema 回答这个问题：把上一步的初始输入作为数学问题计算，"
                "输出 {answer, explanation, confidence}。"
            ),
        ),
        PipelineStep(
            name="summary",
            agent=summary_agent,
            schema_name="summary",
            task_instruction=(
                "请基于上一步的 math 输出（其中 answer 是最终数值），"
                "用 summary schema 写一句话总结（one_liner ≤ 30 字），并给出 3 个要点。"
                '输出 {"one_liner": "...", "key_points": [...], "category": "..."}'
            ),
        ),
    ]
    pipeline = Pipeline(name="math→summary", steps=steps)
    return pipeline


def build_research_to_report_pipeline(ma) -> Pipeline:
    """场景 2：调研 → 报告（用 web 搜索 + 总结专家）

    步骤：
      1. researcher agent: 调研主题 → 输出 {findings, sources, confidence}
      2. writer agent: 把发现写成结构化报告
    """
    researcher = ma.experts.get("general") or ma.router
    writer = ma.experts.get("general") or ma.router

    steps = [
        PipelineStep(
            name="research",
            agent=researcher,
            schema_name="summary",  # 复用 summary schema 表达 key_points
            task_instruction=(
                "请基于上一步输入的问题，给出 3-5 条研究发现（key_points）。"
                "category 填'研究'。"
                '返回 {"one_liner": "研究主题", "key_points": [...], "category": "研究"}'
            ),
        ),
        PipelineStep(
            name="report",
            agent=writer,
            schema_name="summary",
            task_instruction=(
                "请基于上一步的研究发现（key_points），"
                "写一份简短报告：one_liner 给出报告标题，"
                "key_points 列 3 个核心结论。"
                '返回 {"one_liner": "...", "key_points": [...], "category": "报告"}'
            ),
        ),
    ]
    return Pipeline(name="research→report", steps=steps)