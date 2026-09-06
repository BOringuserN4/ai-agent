# -*- coding: utf-8 -*-
"""
01_basic_chat.py — 最简 Agent：连接 DeepSeek，完成一次对话。

目标：跑通「输入 → 发给大模型 → 收到回答」这条最基础的链路。
这一步跑通了，你的 Agent 就已经「活了」，后面只是给它加工具、加记忆。

运行方式：
    python3 01_basic_chat.py
"""
import os

# 1) 从 .env 读取 DEEPSEEK_API_KEY （键名必须和 .env 里一致）
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key or api_key == "sk-your-key-here":
    raise SystemExit("❌ 请在 .env 里填入你的 DEEPSEEK_API_KEY（见 .env）")

# 2) DeepSeek 官方 API 兼容 OpenAI SDK，直接用它
from openai import OpenAI

# DeepSeek 的 base_url 和模型名见官方文档
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

# 3) 发送一次对话
response = client.chat.completions.create(
    model="deepseek-v4-flash-vision-exp",          # DeepSeek-V4
    messages=[
        {"role": "system", "content": "你是一个友好的 AI 助手。"},
        {"role": "user", "content": "用一句话解释什么是 Agent。"},
    ],
    temperature=0.7,
)

# 4) 打印回答
print("AI 回答：")
print(response.choices[0].message.content)
