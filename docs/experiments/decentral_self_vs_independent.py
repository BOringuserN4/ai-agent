# -*- coding: utf-8 -*-
"""去中心化协商专题 · 决定性实验：自评 vs 独立互评（2026/10/06）

假说：solo 自导自演的"互评"因**同一上下文**（知道意图）而替自己圆场；
      真·独立互评（独立上下文，只看产出）能抓出歧义。

设计：
  生产者任务：写一句「如何在App里开启深色模式」的简短操作说明。
  Arm A（自评）：生产者自己评审这句说明"对陌生人清晰吗"。
  Arm B（独立互评）：新 Agent 实例（全新上下文）**只拿到这句说明**，
        模拟"一个没看过界面的用户照它操作"，报告卡在哪 / 是否需提问。

指标：是否暴露出「说明有歧义/信息缺失」。
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

PRODUCE = ("为我们的手机 App 写一句**简短**操作说明："
           "告诉用户「如何开启深色模式」。只写一句话。")

# 生产者：写说明
producer = Agent(system_prompt="你是文案撰写者，输出简洁。")
with contextlib.redirect_stdout(io.StringIO()):
    instruction = producer.run(PRODUCE, max_steps=4)
instruction = (instruction or "").strip()
print("═" * 70)
print("【生产者产出的说明】")
print(" ", instruction)
print("═" * 70)

# Arm A：自评（同一上下文，知道意图）
SELF_REVIEW = ("请评审你刚才写的那句说明："
               "对一个从没见过这个界面的用户，它清晰、可执行吗？"
               "有没有歧义或缺失？给出你的判断。")
with contextlib.redirect_stdout(io.StringIO()):
    a = producer.run(SELF_REVIEW, max_steps=4)
print("\n【Arm A · 自评（同上下文）】")
print((a or "").strip()[:450])

# Arm B：独立互评（全新实例，只给说明）
reviewer = Agent(system_prompt=(
    "你是一个从未用过这个App的普通用户。你只拿到了下面这一句操作说明，"
    "请**严格照它操作**，并报告：你能否顺利完成？卡在哪？需要问什么？"
    "不要脑补界面细节；有不清就问。"))
with contextlib.redirect_stdout(io.StringIO()):
    b = reviewer.run(f"这是操作说明：『{instruction}』\n请照做并报告。", max_steps=4)
print("\n【Arm B · 独立互评（独立上下文，只看产出）】")
print((b or "").strip()[:450])
