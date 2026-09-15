# -*- coding: utf-8 -*-
"""
agent/roles.py — 专业 Agent 角色定义

这里定义多个「不同专长」的 Agent。每个 Agent = 不同系统提示词 + 不同的工具集。
这些是 Multi-Agent 里的基本单元，供上层（如 multi_agent.py 的调度器）使用。

每个角色是一个 dict / 可复用配置。实际运行由 core.Agent 执行。
"""
from agent.core import Agent


# 不同角色的配置。每个 Agent 可指定：名称、系统提示词、是否带工具。
def build_math_agent():
    """数学 Agent：擅长所有计算。"""
    return Agent(
        system_prompt=(
            "你是「数学专家」。你的职责是解答所有数学/计算/数据类问题。"
            "遇到计算务必调用 calculator 工具，算完用一句话总结结果。"
            "你只处理数学问题，其他问题回答'这不属于我的专长'。"
        ),
        # 给这个 Agent 专属的工具（数学只用计算器 + 时间）
        tools=("calculator", "current_time"),
    )


def build_weather_agent():
    """天气 Agent：擅长查询天气。"""
    return Agent(
        system_prompt=(
            "你是「天气专家」。你的职责是查询城市天气。"
            "遇到城市天气问题，调用 get_weather 工具获取实时数据。"
            "你只处理天气相关，其他问题回答'这不属于我的专长'。"
        ),
        tools=("get_weather", "current_time"),
    )


def build_general_agent():
    """通用 Agent：什么都聊，但无工具或仅基础工具。"""
    return Agent(
        system_prompt="你是一个友好的通用助手，能回答常识、百科、日常问题。",
        tools=("current_time",),
    )


def build_solo_agent():
    """全能 Agent（2026/09/15）：不拆任务时的默认执行者。

    为什么需要它：math/weather/general 都是「专才」，各自只有部分工具。
    一旦 Router 判定「不需要拆」，指派给任何一个专才都会漏答一半
    （math 查不了天气、general 连计算器都没有）。所以需要一个工具全开的执行者。
    """
    return Agent(
        system_prompt=(
            "你是一个全能助手，能同时处理计算、天气、常识等各类问题。"
            "遇到计算务必调用 calculator，遇到天气务必调用 get_weather。"
            "用户提了多件事时，逐件办完再统一回答，不要漏掉任何一件。"
        ),
        tools=None,  # None = 全部工具（calculator / get_weather / current_time）
    )


# 供调度器查询的注册表：角色名 -> 构建函数
ROLE_FACTORIES = {
    "solo": build_solo_agent,     # 全能（默认）
    "math": build_math_agent,
    "weather": build_weather_agent,
    "general": build_general_agent,
}
