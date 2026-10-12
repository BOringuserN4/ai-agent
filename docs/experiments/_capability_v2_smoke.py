# -*- coding: utf-8 -*-
"""能力×编排 v2 环境冒烟（2026/10/12）

目的：跑预筛之前，先确认两条模型臂今天都能调通（强=deepseek-flash / 弱=qwen-turbo）。
不涉及任何题目选择或结论，只是把跑道铺好。
"""
import os, sys, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from openai import OpenAI
from agent.core import Agent

_DASH = OpenAI(api_key=os.getenv("DASHSCOPE_API_KEY"),
               base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

ARMS = [("strong/deepseek-flash", dict(model="deepseek-flash", client=None)),
        ("weak/qwen-turbo",       dict(model="qwen-turbo", client=_DASH))]

Q = "只回答一个数字：17 × 23 = ?"
for name, cfg in ARMS:
    try:
        a = Agent(system_prompt="你是简洁的算术助手。", model=cfg["model"], client=cfg["client"])
        with contextlib.redirect_stdout(io.StringIO()):
            out = a.run(Q, max_steps=2) or ""
        print(f"OK\t{name}\t{str(out)[:80]}", flush=True)
    except Exception as e:
        print(f"FAIL\t{name}\t{type(e).__name__}: {e}", flush=True)
