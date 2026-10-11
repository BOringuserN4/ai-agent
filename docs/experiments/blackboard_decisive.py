# -*- coding: utf-8 -*-
"""Blackboard 专题 · 决定性实验：大动作空间 + 步数预算（2026/10/11）

第一轮失败原因：动作空间仅 5 个组件 → 预排臂可**穷举**，覆盖了所有可能。
本实验放大到 **20 个组件**（跨 4 个子系统），并给**步数预算**：
  · 穷举不可行（20 个 inspect 超预算）；
  · 只有**顺着线索走**才能在预算内定位根因。

线索设计：
  · query_logs() 给出**子系统级**线索（4 个子系统之一有错）；
  · inspect(component) 在子系统内逐个缩小 —— 但盲目全查会超预算。

对照：
  · 预排臂：看到结果前一次性列出序列（无法知道是哪个子系统 → 只能瞎顺序）
  · 迭代臂（黑板式）：先看线索 → 只在**被指出的子系统**里查
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
ALL = [(s, c) for s, cs in SUBSYS.items() for c in cs]   # 20 个
BUDGET = 7            # 步数预算：穷举 20 个不可能

PRIMARY = "order-api 今早开始报 500。请定位**根因组件**（20 个组件之一）。"
SPEC = [
    {"type": "function", "function": {"name": "check_alerts", "description": "查看告警",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "query_logs", "description": "查看错误日志（给出子系统级线索）",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "inspect", "description": "检查某组件",
        "parameters": {"type": "object", "properties": {"component": {"type": "string"}}, "required": ["component"]}}},
]


def build(root_comp):
    root_sys = next(s for s, cs in SUBSYS.items() if root_comp in cs)
    def check_alerts():
        return "order-api: 500 错误率 12%；其他服务普通告警"
    def query_logs():
        return f"order-api 错误日志：异常指向「{root_sys}」子系统（如 {SUBSYS[root_sys][0]} 等）"
    def inspect(component):
        c = (component or "").strip()
        return "❌ 确认异常（根因）" if c == root_comp else "✅ 正常"
    return {"check_alerts": check_alerts, "query_logs": query_logs, "inspect": inspect}, root_sys


def parse_calls(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("calls", [])
    except Exception:
        return []


def safe_call(fn, args):
    """调用工具，**忽略多余参数**（模型可能多塞键）。不完善则报错。"""
    import inspect as _ins
    try:
        ok = set(_ins.signature(fn).parameters)
        args = {k: v for k, v in (args or {}).items() if k in ok}
    except Exception:
        pass
    try:
        return fn(**args)
    except Exception as e:
        return f"调用失败: {e}"


def arm_preplanned(root_comp):
    tools, root_sys = build(root_comp)
    planner = Agent(system_prompt=(
        "你是运维负责人。在**看到任何结果前**，一次性列出完整诊断序列，最多 " + str(BUDGET) + " 步。"
        "工具：check_alerts()、query_logs()、inspect(component)。可选组件（20 个，名称精确）："
        + ", ".join(c for _, c in ALL) +
        "。只输出 JSON {\"calls\":[{\"tool\":..,\"args\":{..}}]}。"))
    planner.tools_spec, planner.tool_registry = [], {}
    with contextlib.redirect_stdout(io.StringIO()):
        plan = planner.run(PRIMARY, max_steps=1) or ""
    calls = parse_calls(plan)[:BUDGET]
    results = []
    for c in calls:
        fn = tools.get(c.get("tool"))
        results.append((c, safe_call(fn, c.get("args", {})) if fn else "未知工具"))
    dec = Agent(system_prompt="你是运维负责人。基于检测结果给出根因组件名。")
    dec.tools_spec, dec.tool_registry = [], {}
    txt = "\n".join(f"{c} -> {r}" for c, r in results) or "（无）"
    with contextlib.redirect_stdout(io.StringIO()):
        concl = dec.run(f"{PRIMARY}\n\n结果：\n{txt}\n\n根因组件名？只回答名称。", max_steps=1) or ""
    return concl, len(calls), planner.usage["total_tokens"] + dec.usage["total_tokens"]


def arm_iterative(root_comp):
    tools, _ = build(root_comp)
    a = Agent(system_prompt=(
        f"你是运维负责人。你有一块状态板，最多 {BUDGET} 步。"
        "先看告警/日志拿到线索，再**只在被指出的子系统内**逐个 inspect，定位根因组件名。"))
    a.tools_spec, a.tool_registry = SPEC, tools
    with contextlib.redirect_stdout(io.StringIO()):
        concl = a.run(PRIMARY, max_steps=BUDGET) or ""
    n = sum(1 for s in a.tracer.steps if s.type == "tool_call")
    return concl, n, a.usage["total_tokens"]


if __name__ == "__main__":
    n = int(os.getenv("BB_N", "4"))
    rng = random.Random(20261011)
    print(f"动作空间={len(ALL)} 组件  步数预算={BUDGET}")
    print(f"{'根因':<14}{'系统':<6}{'预排:正确':<10}{'预排:调用':<10}{'迭代:正确':<10}{'迭代:调用'}")
    print("-" * 66)
    ph = ih = pc = ic = 0
    for i in range(n):
        root_comp = rng.choice([c for _, c in ALL])
        _, root_sys = build(root_comp)
        p, pcn, _ = arm_preplanned(root_comp)
        it, icn, _ = arm_iterative(root_comp)
        ph += root_comp in p; ih += root_comp in it
        pc += pcn; ic += icn
        print(f"{root_comp:<14}{root_sys:<6}{('✅' if root_comp in p else '❌'):<10}{pcn:<10}"
              f"{('✅' if root_comp in it else '❌'):<10}{icn}")
    print("-" * 66)
    print(f"正确率：预排 {ph}/{n} ｜ 迭代 {ih}/{n}")
    print(f"平均调用：预排 {pc/n:.1f} ｜ 迭代 {ic/n:.1f}")
