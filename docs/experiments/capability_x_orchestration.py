# -*- coding: utf-8 -*-
"""能力 × 编排 对照实验（2026/10/11）

要验的因果：**「编排脚手架的增益，是否随模型能力提升而衰减」**。
（前面 Debate/显式规划/黑板都指向这个方向，但一直缺「弱模型对照」这块直接证据。）

设计：同一批任务 × 两种模型 × 两种编排
  · 模型：强 = deepseek-flash ｜ 弱 = qwen-turbo（DashScope）
  · 编排：① solo（单 Agent 直答）② EC（生成→批判→重做，2 轮）
  · 任务：多约束技术选型（有客观要点清单，可确定性打分）

指标：要点命中数（0~6）。看 **Δ = EC − solo** 在强弱模型上的差异。
预期（待验）：弱模型 Δ 明显 > 强模型 Δ（若成立，即为「能力吃掉脚手架」的直接证据）。
"""
import os, sys, io, re, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from openai import OpenAI
from agent.core import Agent

STRONG = dict(model="deepseek-flash", client=None)   # None → 默认 DeepSeek 客户端
_DASH = OpenAI(api_key=os.getenv("DASHSCOPE_API_KEY"),
               base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
WEAK = dict(model="qwen-turbo", client=_DASH)

TASKS = {
    "T1_嵌入式排序": (
        "为嵌入式实时设备（RAM 256KB、约 10 万条记录、数据几乎已按时间有序、"
        "要求稳定排序、最坏耗时须可预测）在「快速排序/归并排序/堆排序」中选一种。"
        "请说明选择理由与注意点。",
        {"近乎有序": ["几乎已", "近乎有序", "接近有序", "已排序", "自然合并", "Timsort"],
         "最坏可预测": ["最坏", "退化", "O(n²)", "O(n^2)", "可预测", "内省", "introsort"],
         "稳定性": ["稳定", "相对顺序"],
         "空间": ["空间", "原地", "内存", "RAM", "256"],
         "缓存/常数": ["缓存", "常数", "局部性", "分支"],
         "给明确方案": ["建议", "推荐", "采用", "应该选", "选择"]},
    ),
    "T2_缓存层决策": (
        "一个读多写少的商品详情服务（QPS 5000、数据变更每 5 分钟一次、"
        "要求强一致读、已有 Redis 集群）该不该加缓存层？给出明确建议与理由。",
        {"一致性": ["一致", "强一致", "脏读", "过期", "失效"],
         "读写比": ["读多写少", "读多", "读远多于写"],
         "失效策略": ["失效", "TTL", "过期", "主动更新", "双写"],
         "成本/复杂度": ["复杂度", "成本", "运维", "收益"],
         "现有资源": ["Redis", "已有"],
         "给明确方案": ["建议", "推荐", "应该", "结论"]},
    ),
}


def make(model_cfg, sys_prompt):
    return Agent(system_prompt=sys_prompt,
                 model=model_cfg["model"], client=model_cfg["client"])


def score(text, spec):
    return sum(1 for _, ws in spec.items() if any(w in (text or "") for w in ws))


def arm_solo(cfg, task, spec):
    a = make(cfg, "你是资深系统工程师，给出明确的技术建议与理由。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(task, max_steps=3) or ""
    return score(out, spec)


def arm_ec(cfg, task, spec, rounds=2):
    """生成 → 批判 → 重做（就地实现，2 轮）。"""
    gen = make(cfg, "你是资深系统工程师，给出明确的技术建议与理由。")
    with contextlib.redirect_stdout(io.StringIO()):
        ans = gen.run(task, max_steps=3) or ""
    for _ in range(rounds - 1):
        critic = make(cfg, "你是严格的评审专家。只指出这份回答**遗漏或含糊**的关键点，简短列 3 条。")
        with contextlib.redirect_stdout(io.StringIO()):
            crit = critic.run(f"任务：{task}\n\n回答：\n{ans}\n\n它遗漏了哪些关键点？", max_steps=2) or ""
        fixer = make(cfg, "你是资深系统工程师。根据评审意见补全回答，给出更完整、明确的技术建议。")
        with contextlib.redirect_stdout(io.StringIO()):
            ans = fixer.run(f"任务：{task}\n\n原回答：\n{ans}\n\n评审意见：\n{crit}\n\n请补全。",
                            max_steps=3) or ""
    return score(ans, spec)


RESULT_FILE = os.path.join(ROOT, "tmp-artifacts", "capability_x_results.txt")


def _load_done():
    """读已完成的格子（可续跑）：返回 {(task, model): (solo, ec)}。"""
    done = {}
    if os.path.exists(RESULT_FILE):
        for ln in open(RESULT_FILE, encoding="utf-8"):
            m = re.match(r"CELL\t(.+?)\t(.+?)\t([\d.]+)\t([\d.]+)", ln.strip())
            if m:
                done[(m.group(1), m.group(2))] = (float(m.group(3)), float(m.group(4)))
    return done


if __name__ == "__main__":
    n = int(os.getenv("CAP_N", "2"))
    done = _load_done()
    print(f"（已完成 {len(done)} 格，续跑）", flush=True)
    rows = {}
    for tname, (task, spec) in TASKS.items():
        for mname, cfg in (("弱(qwen-turbo)", WEAK), ("强(deepseek-flash)", STRONG)):
            key = (tname, mname)
            if key in done:
                s_avg, e_avg = done[key]
                rows[key] = (s_avg, e_avg)
                print(f"{tname:<14}{mname:<20}solo={s_avg:.1f}  EC={e_avg:.1f}  Δ={e_avg-s_avg:+.1f}  （已存）", flush=True)
                continue
            s_tot = e_tot = 0
            for _ in range(n):
                s_tot += arm_solo(cfg, task, spec)
                e_tot += arm_ec(cfg, task, spec)
            s_avg, e_avg = s_tot / n, e_tot / n
            rows[key] = (s_avg, e_avg)
            # 增量落盘（每格完成即写，防会话回收丢结果）
            with open(RESULT_FILE, "a", encoding="utf-8") as fh:
                fh.write(f"CELL\t{tname}\t{mname}\t{s_avg:.1f}\t{e_avg:.1f}\n")
                fh.flush()
            print(f"{tname:<14}{mname:<20}solo={s_avg:.1f}  EC={e_avg:.1f}  Δ={e_avg-s_avg:+.1f}", flush=True)
    print("\n" + "=" * 62, flush=True)
    print("Δ（EC − solo）汇总：", flush=True)
    for mname in ("弱(qwen-turbo)", "强(deepseek-flash)"):
        ds = [rows[(t, mname)][1] - rows[(t, mname)][0] for t in TASKS if (t, mname) in rows]
        if ds:
            print(f"  {mname:<20}平均 Δ = {sum(ds)/len(ds):+.2f}  （各任务：{['%+.1f' % x for x in ds]}）", flush=True)
