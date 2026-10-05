# -*- coding: utf-8 -*-
"""层级编排专题 · 第 2 步：证明单层结构是否露馅（2026/10/05）

方向 A：「子任务自身可再拆」——多城/多对象的同域子任务
方向 B：「需要复查闸」——规划容易错、且无人拦

观察：
  · Router（_plan）产出什么（扁平？漏拆？合并错？）
  · 端到端结果是否完整
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.multi_agent import MultiAgent

CASES = {
    "A1_三城分头调研": (
        "请分头调研北京、上海、广州三个城市，每个城市都要给出当前气温，"
        "并判断该城市此刻是否适合户外活动（气温 15~28℃ 为适宜）。"
        "最后给出三城的对比结论。"
    ),
    "A2_嵌套报告": (
        "帮我做一份《天气出行报告》，分三部分：\n"
        "（1）数据采集：分别查北京、上海、广州、深圳四城气温；\n"
        "（2）对比分析：算四城平均气温、找出最暖与最冷；\n"
        "（3）出行建议：基于上面结论给一句建议。"
    ),
    "B1_伪跨域陷阱": (
        "帮我算一下 (12+8)*3 等于多少。"
    ),
    "B2_易错规划": (
        "先查北京今天的气温，再基于这个气温值判断穿衣建议"
        "（<10℃ 羽绒服、10~20℃ 外套、>20℃ 短袖）。"
    ),
}


def probe(name, task):
    print(f"\n{'#'*72}\n# 案例 {name}\n{'#'*72}")
    ma = MultiAgent(use_memory=False)
    # 直接看 Router 的规划产出（不执行）
    tasks = ma._plan(task)
    print(f"[_plan 产出] {len(tasks)} 个子任务：")
    for t in tasks:
        print(f"    expert={t['expert']:8s} subtask={t['subtask'][:60]}")
    experts = [t["expert"] for t in tasks]
    print(f"[去重后专家] {experts}")

    # 端到端
    ans = ma.run(task)
    print(f"\n[最终回答]\n{(ans or '').strip()[:400]}")
    return tasks, ans


if __name__ == "__main__":
    for name, task in CASES.items():
        probe(name, task)
