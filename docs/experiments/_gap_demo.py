# -*- coding: utf-8 -*-
"""能力×编排 v2 · mini 预筛（2026/10/14）

目的：验证「弱模型能在什么题上真掉分」——即找「有区分度」的题。
设计：6 道**客观算账题**（唯一数值答案，确定性判分），只跑 solo × 两模型。
不涉及 EC 臂；产出一张 gap 表。正式题集由用户定，本脚本只是演示「区分度」。
"""
import os, sys, io, re, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from openai import OpenAI
from agent.core import Agent

_DASH = OpenAI(api_key=os.getenv("DASHSCOPE_API_KEY"),
               base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
# 弱臂模型可用环境变量覆盖（2026/10/14：qwen-turbo 遇 DashScope 模型级 429，暂换 qwen-flash）
WEAK_MODEL = os.getenv("WEAK_MODEL", "qwen-flash")
ARMS = [(f"强/deepseek", dict(model="deepseek-flash", client=None)),
        (f"弱/{WEAK_MODEL}", dict(model=WEAK_MODEL, client=_DASH))]

# (编号, 题面, 期望答案, 容差)
TASKS = [
    ("T1_实例数", "某服务每日请求 8.64 亿次，平均每次请求产生 5 次 DB 查询；"
                  "单个 DB 实例上限 8000 QPS。要求 30% 冗余，最少需要几个 DB 实例？"
                  "只输出一个整数。", 9.0, 0.01),
    ("T2_随机写耗时", "磁盘随机写 2000 IOPS（每次 4KB）。要把 10GB 数据以随机 4KB 小块写入（忽略其他开销），"
                  "耗时多少秒？只输出一个整数。", 1311.0, 1.0),
    ("T3_在途请求", "三个服务串联，平均延迟分别为 12ms / 30ms / 8ms；流量 400 req/s。"
                  "按 Little's Law，该链路平均在途请求数是多少？只输出一个数（保留一位小数）。", 20.0, 0.05),
    ("T4_平均延迟", "接口 P50=10ms、P99=500ms，请求量 1000/s。若只有 1% 的请求达到 P99 水平，"
                  "其余按 P50，平均延迟是多少毫秒？只输出一个数（保留一位小数）。", 14.9, 0.05),
    ("T5_扩容核数", "某服务当前 4 核、CPU 利用率 25%。流量翻倍后，要求利用率不超过 50%，"
                  "最少需要几核？只输出一个整数。", 4.0, 0.01),
    ("T6_后端降幅", "某接口缓存命中率从 80% 提升到 90%，后端负载下降百分之几？只输出一个数。", 50.0, 0.01),
]

OUT = os.path.join(ROOT, "tmp-artifacts", "gap_demo.txt")
def last_num(text):
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    return float(nums[-1]) if nums else None

def run_one(cfg, task):
    a = Agent(system_prompt="你是严谨的系统工程师。只输出要求的那个数字，不要解释。",
              model=cfg["model"], client=cfg["client"])
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(task, max_steps=2) or ""
    return out

if __name__ == "__main__":
    N = int(os.getenv("GAP_N", "1"))
    results = {}
    for tname, task, expect, tol in TASKS:
        row = {}
        for mname, cfg in ARMS:
            hits, statuses = 0, []
            for _ in range(N):
                try:
                    out = run_one(cfg, task)
                    got = last_num(out)
                    if got is None:
                        status = "RAN_NO_NUM" if (out or "").strip() else "EMPTY"
                    else:
                        status = "OK" if abs(got - expect) <= tol else f"WRONG({got})"
                    ok = status == "OK"
                except Exception as e:
                    ok, status = False, f"ERR:{type(e).__name__}"
                hits += 1 if ok else 0
                statuses.append(status)
                # 增量落盘（可续跑/抗会话回收）
                with open(OUT, "a", encoding="utf-8") as fh:
                    fh.write(f"RAW\t{tname}\t{mname}\t{status}\n"); fh.flush()
            row[mname] = (hits, statuses)
        results[tname] = (expect, row)
        line = f"{tname:<16}"
        for mname, _ in ARMS:
            hits, statuses = row[mname]
            line += f" | {mname}: {hits}/{N} {statuses}"
        print(line, flush=True)
    print("\n" + "=" * 70, flush=True)
    for mname, _ in ARMS:
        hits = sum(r[mname][0] for _, (_, r) in results.items())
        errs = sum(1 for _, (_, r) in results.items() for s in r[mname][1] if s.startswith("ERR"))
        print(f"{mname}: solo 答对 {hits}/{len(TASKS)*N}  （基础设施故障 {errs} 次，不计入）", flush=True)
