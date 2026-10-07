# -*- coding: utf-8 -*-
"""Contract Net 专题 · 探针（2026/10/07）

方向 C「需求未知」：中央无法评估「这活该谁干」，执行者自己知道。

设计：
  · 三位工程师各持**私有信息**（当前负载 / 能力 / 真实工期估计）—— 互相看不到；
  · 中央只看到「名字 + 一句简介」，不知道谁最合适；
  · 真值（谁最优）**随机**，且只有综合私有信息才能定 → 中央只能猜。

对照：
  集中式臂：单 Agent，直接「派给某人」（无报价）
  报价臂（Contract Net）：公告任务 → 三人各自报价 → 中央按报价择优

指标：派对人（== 真值）的比例。
"""
import os, sys, io, random, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

NAMES = ["甲", "乙", "丙"]
TRIALS = int(os.getenv("CN_TRIALS", "4"))


def scenario(rng, best=None):
    """随机决定谁最优（负载低 + 擅长），返回 (task, briefs, privates, truth)。

    best 可显式指定（修正真值分布偏斜：改为轮转）。
    """
    if best is None:
        best = rng.choice(NAMES)
    task = "公司有一台 Flink 实时管道的消费延迟异常（积压 ~2 小时），需要一位工程师接手排查并修复。"
    # 私有信息：最优者 = 擅长 + 空闲；其余各有短板
    others = [n for n in NAMES if n != best]
    rng.shuffle(others)
    hard1, hard2 = others
    privates = {
        best: "你的私有信息：你**精通 Flink**，当前**无其他任务**，预估 **1 天**可定位修复。",
        hard1: "你的私有信息：你**不熟 Flink**（只做过 Spark），且手头有**两个 deadline 今晚到期**，预估至少 5 天。",
        hard2: "你的私有信息：你懂一点 Flink 但**不深**，正在**休假中**（明天起三天不在），预估 3 天且需远程。",
    }
    # 中央只看到这些"简介"（都长得差不多，无法区分）
    briefs = {n: f"{n}：数据平台工程师，工龄 {rng.randint(3, 6)} 年，参与过若干数据项目。" for n in NAMES}
    return task, briefs, privates, best


def arm_central(task, briefs):
    desc = "\n".join(f"  {n}：{d}" for n, d in briefs.items())
    a = Agent(system_prompt="你是团队负责人。你必须指派一位工程师，且只能依据给你的简介。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = a.run(f"{task}\n\n可指派人员：\n{desc}\n\n请直接指定一位（只回答『派给 X』）。", max_steps=3) or ""
    return out


def arm_contract_net(task, briefs, privates):
    # 1) 公告
    desc = "\n".join(f"  {n}：{d}" for n, d in briefs.items())
    announce = f"【任务公告】{task}\n\n候选：\n{desc}\n\n请各位**报价**：能否承接、预计工期、当前是否有空。"
    bids = {}
    for n in NAMES:
        eng = Agent(system_prompt=f"你是工程师「{n}」。{privates[n]}\n"
                                  f"面对任务公告，如实报价（能否做 / 工期 / 是否空闲）。简短。")
        with contextlib.redirect_stdout(io.StringIO()):
            bids[n] = (eng.run(announce, max_steps=2) or "").strip()
    # 2) 择优（只看报价）
    bid_text = "\n".join(f"【{n}报价】{b}" for n, b in bids.items())
    mgr = Agent(system_prompt="你是负责人。只依据各人报价，选出最能胜任、工期最短的一位。")
    with contextlib.redirect_stdout(io.StringIO()):
        out = mgr.run(f"{task}\n\n各人报价：\n{bid_text}\n\n选出中标者（只回答『派给 X』）。", max_steps=2) or ""
    return out, bids


def pick(text):
    """从回答里解析选择：优先『派给X』，其次『我选/选/指定 X』，最后取首个出现的人名。"""
    if not text:
        return None
    import re
    for pat in (r"派给\s*([甲乙丙])", r"(?:我选|选定|指定|选择)\s*\**\s*([甲乙丙])"):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    found = [n for n in NAMES if n in text]
    return found[0] if found else None


if __name__ == "__main__":
    rng = random.Random(20261007)
    print(f"{'#':<4}{'真值':<6}{'集中式':<8}{'报价臂':<8}")
    print("-" * 30)
    c_ok = b_ok = 0
    for t in range(TRIALS):
        # 修正：真值轮转（甲→乙→丙…），保证覆盖均匀，避免偏斜虚高
        task, briefs, privates, truth = scenario(rng, best=NAMES[t % len(NAMES)])
        co = arm_central(task, briefs)
        bo, _ = arm_contract_net(task, briefs, privates)
        c_pick = pick(co)
        b_pick = pick(bo)
        c_ok += c_pick == truth
        b_ok += b_pick == truth
        print(f"{t+1:<4}{truth:<6}"
              f"{str(c_pick) + ('✅' if c_pick == truth else '❌'):<8}"
              f"{str(b_pick) + ('✅' if b_pick == truth else '❌'):<8}")
    print("\n" + "=" * 30)
    print(f"集中式  : {c_ok}/{TRIALS} = {c_ok/TRIALS:.0%}")
    print(f"Contract Net: {b_ok}/{TRIALS} = {b_ok/TRIALS:.0%}")
