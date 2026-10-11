# -*- coding: utf-8 -*-
"""Blackboard 专题 · 终版实验（确定性指标，2026/10/11）

前两版打分器都有缺陷：
  v1 `root in 结论` → 枚举所有查过组件 → 假阳性；
  v2 解析"最终宣告" → 模型**猜中未验证的组件**也算对 → 仍是假阳性。

本版彻底去掉文本解析，改用**确定性指标**：
    ✅ 判对 ⟺ **某次 inspect 真的返回了根因标记**（"确认异常"）。
  —— 与模型怎么说无关；没查到就是没查到。

设计（保持）：
  · 20 组件 / 4 子系统；inspect 预算 3（监控/日志免费）；
  · 预排臂：看不到日志就盲定 3 个 inspect（不知子系统）；
  · 黑板臂：日志指出子系统 → 只在该子系统 5 个组件内 inspect。
"""
import os, sys, io, json, random, re, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

SUBSYS = {
    "计算": ["order-api", "payment-svc", "user-svc", "gateway", "worker"],
    "存储": ["mysql-main", "redis-cache", "kafka", "es-search", "minio"],
    "网络": ["dns", "lb-nginx", "vpn", "cdn", "firewall"],
    "宿主": ["node-01", "node-02", "node-03", "disk-vol", "container-rt"],
}
ALL = [(s, c) for s, cs in SUBSYS.items() for c in cs]
INSPECT_BUDGET = 3
ROOT_MARK = "确认异常"
PRIMARY = "order-api 今早开始报 500。请定位**根因组件**（20 个组件之一）。"
SPEC_INSPECT = {"type": "function", "function": {"name": "inspect", "description": "检查某组件（昂贵，预算 3 次）",
    "parameters": {"type": "object", "properties": {"component": {"type": "string"}}, "required": ["component"]}}}


class Budget:
    def __init__(self, n): self.left = n
    def take(self):
        if self.left <= 0: return False
        self.left -= 1; return True


def make_inspect(root_comp, budget):
    def inspect(component):
        if not budget.take():
            return "❌ 诊断预算已用尽"
        c = (component or "").strip()
        return f"{c}: ❌ 确认异常（根因）" if c == root_comp else f"{c}: ✅ 正常"
    return inspect


def parse_calls(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m: return []
    try: return json.loads(m.group(0)).get("calls", [])
    except Exception: return []


def _args_ok(fn, args):
    import inspect as _i
    try: ok = set(_i.signature(fn).parameters)
    except Exception: return args or {}
    return {k: v for k, v in (args or {}).items() if k in ok}


def run_preplanned(root_comp, root_sys):
    """盲计划：看不到日志，先列 3 个 inspect。"""
    b = Budget(INSPECT_BUDGET)
    ins = make_inspect(root_comp, b)
    planner = Agent(system_prompt=(
        "你是运维负责人。在**看到任何结果前**，直接列出最多 " + str(INSPECT_BUDGET) +
        " 个要 inspect 的组件（你**还不知道**异常属于哪个子系统）。可选组件：" +
        ", ".join(c for _, c in ALL) + "。只输出 JSON {\"calls\":[{\"tool\":\"inspect\",\"args\":{\"component\":\"..\"}}]}。"))
    planner.tools_spec, planner.tool_registry = [], {}
    with contextlib.redirect_stdout(io.StringIO()):
        plan = planner.run(PRIMARY, max_steps=1) or ""
    calls = [c for c in parse_calls(plan) if c.get("tool") == "inspect"][:INSPECT_BUDGET]
    confirmed = False
    for c in calls:
        r = ins(**_args_ok(ins, c.get("args")))
        confirmed = confirmed or (ROOT_MARK in r)
    return confirmed, len(calls)


def run_blackboard(root_comp, root_sys):
    """黑板：日志（免费）指出子系统 → 专家只在 5 个组件内 inspect。

    ⚠️ 控制实验：**打乱组件顺序**，排除「根因恰好在列表前列」的位置红利。
    """
    b = Budget(INSPECT_BUDGET)
    ins = make_inspect(root_comp, b)
    comps = list(SUBSYS[root_sys])
    random.Random(hash(root_comp) & 0xffff).shuffle(comps)   # 打乱顺序
    _board = [f"告警：order-api 500 错误率 12%", f"日志：异常指向「{root_sys}」子系统"]
    expert = Agent(system_prompt=(
        f"你是「{root_sys}」子系统专家。黑板已指出异常属于你的子系统。"
        f"你可 inspect 的组件仅限：{'、'.join(comps)}。"
        f"请在预算内检查，找出确认异常的组件。"))
    expert.tools_spec, expert.tool_registry = [SPEC_INSPECT], {"inspect": ins}
    with contextlib.redirect_stdout(io.StringIO()):
        expert.run(f"{PRIMARY}\n\n【黑板】\n" + "\n".join(_board) +
                   f"\n\n请在 {'、'.join(comps)} 内定位根因。", max_steps=INSPECT_BUDGET)
    confirmed = any(
        (s.type == "tool_result" and s.tool == "inspect" and ROOT_MARK in str(s.result or ""))
        for s in expert.tracer.steps)
    return confirmed


def run_iterative_single(root_comp, root_sys):
    """对照臂：**单个迭代 Agent**（同样先看日志再反应，但不是多 Agent 黑板）。

    这是决定性控制：若它也能达到黑板水平，则优势来自「反应式控制」，而非「黑板/多 Agent」。
    """
    b = Budget(INSPECT_BUDGET)
    ins = make_inspect(root_comp, b)
    tools = {"check_alerts": lambda: "order-api: 500 错误率 12%",
             "query_logs": lambda: f"order-api 错误日志：异常指向「{root_sys}」子系统",
             "inspect": ins}
    SPEC_ALL = [{"type": "function", "function": {"name": "check_alerts", "description": "查看告警", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "query_logs", "description": "查看错误日志", "parameters": {"type": "object", "properties": {}}}},
                SPEC_INSPECT]
    a = Agent(system_prompt=(
        f"你是运维负责人。你可自行调用工具排查：先看告警/日志，再 inspect 候选组件（预算 3 次）。"
        f"全部候选组件（20 个）：{'、'.join(c for _, c in ALL)}。请自己决定查哪些。"))
    a.tools_spec, a.tool_registry = SPEC_ALL, tools
    with contextlib.redirect_stdout(io.StringIO()):
        a.run(PRIMARY, max_steps=6)
    return any((s.type == "tool_result" and s.tool == "inspect" and ROOT_MARK in str(s.result or ""))
               for s in a.tracer.steps)


if __name__ == "__main__":
    n = int(os.getenv("BB_N", "8"))
    rng = random.Random(20261011)
    print(f"动作空间={len(ALL)} 组件  inspect 预算={INSPECT_BUDGET}  指标=「根因是否被 inspect 验证」")
    print(f"{'根因':<14}{'系统':<6}{'静态预排':<10}{'单Agent反应':<12}{'黑板'}")
    print("-" * 54)
    ph = ih = bh = 0
    for i in range(n):
        root_comp = rng.choice([c for _, c in ALL])
        root_sys = next(s for s, cs in SUBSYS.items() if root_comp in cs)
        pc, _ = run_preplanned(root_comp, root_sys)
        ic = run_iterative_single(root_comp, root_sys)
        bc = run_blackboard(root_comp, root_sys)
        ph += pc; ih += ic; bh += bc
        print(f"{root_comp:<14}{root_sys:<6}{('✅' if pc else '❌'):<10}"
              f"{('✅' if ic else '❌'):<12}{('✅' if bc else '❌')}")
    print("-" * 54)
    print(f"验证到根因：静态预排 {ph}/{n} ｜ 单Agent反应 {ih}/{n} ｜ 黑板 {bh}/{n}")
