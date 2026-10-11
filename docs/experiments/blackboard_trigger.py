# -*- coding: utf-8 -*-
"""Blackboard 专题 · 收官实验：事件触发 vs 预排（严格预算版，2026/10/11）

前两轮的缺陷：
  · 轮1：动作空间仅 5 组件 → 可穷举；
  · 轮2：预算按「步数」算，被「一步塞多次调用」绕过（老坑）。

本实验：
  · 20 组件 / 4 子系统；**严格封顶工具调用数 = 4**（每次调用计数，超限即拒）；
  · 症状（日志）**只揭示子系统**，不揭示具体组件（子系统内 5 个组件要逐个查）；
  · 真·黑板语义：**症状写入黑板 → 匹配的子系统专家被触发 → 它只在自家子系统内查**
    （无中央调度；谁上由黑板状态决定）。
  · 预排臂：中央在**看到症状之前**决定序列（不知道哪个子系统 → 只能瞎猜）。

预期（待验）：4 步预算下，预排几乎不可能命中（20 选 1）；黑板能聚焦到子系统（5 选 1）。
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
BUDGET = 4                     # ★ 严格工具调用预算

PRIMARY = "order-api 今早开始报 500。请定位**根因组件**（20 个组件之一）。"
SPEC = [
    {"type": "function", "function": {"name": "check_alerts", "description": "查看告警",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "query_logs", "description": "查看错误日志",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "inspect", "description": "检查某组件",
        "parameters": {"type": "object", "properties": {"component": {"type": "string"}}, "required": ["component"]}}},
]


class Budget:
    """严格工具调用预算（跨步累计，防「一步多调用」绕过）。"""
    def __init__(self, n):
        self.left = n
    def take(self):
        if self.left <= 0:
            return False
        self.left -= 1
        return True


def make_tools(root_comp, root_sys, budget):
    def check_alerts():
        if not budget.take():
            return "❌ 预算已用尽"
        return "order-api: 500 错误率 12%；其他服务无异常"
    def query_logs():
        if not budget.take():
            return "❌ 预算已用尽"
        return f"order-api 错误日志：异常指向「{root_sys}」子系统"
    def inspect(component):
        if not budget.take():
            return "❌ 预算已用尽"
        c = (component or "").strip()
        return "❌ 确认异常（根因）" if c == root_comp else "✅ 正常"
    return {"check_alerts": check_alerts, "query_logs": query_logs, "inspect": inspect}


def parse_calls(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0)).get("calls", [])
    except Exception:
        return []


def arm_preplanned(root_comp, root_sys):
    """中央在看到症状前决定序列（静态 workflow）。"""
    budget = Budget(BUDGET)
    tools = make_tools(root_comp, root_sys, budget)
    planner = Agent(system_prompt=(
        "你是运维负责人。在**看到任何结果之前**，一次性列出诊断调用序列，最多 "
        + str(BUDGET) + " 次调用。工具：check_alerts()、query_logs()、inspect(component)。"
        "可选组件：" + ", ".join(c for _, c in ALL) +
        "。只输出 JSON {\"calls\":[{\"tool\":..,\"args\":{..}}]}。"))
    planner.tools_spec, planner.tool_registry = [], {}
    with contextlib.redirect_stdout(io.StringIO()):
        plan = planner.run(PRIMARY, max_steps=1) or ""
    calls = parse_calls(plan)
    results = []
    for c in calls:
        if budget.left <= 0:
            break
        fn = tools.get(c.get("tool"))
        args = c.get("args", {}) or {}
        try:
            r = fn(**{k: v for k, v in args.items()
                      if k in (fn.__code__.co_varnames[:fn.__code__.co_argcount] if fn else ())}) if fn else "未知工具"
        except Exception as e:
            r = f"调用失败: {e}"
        results.append((c, r))
    dec = Agent(system_prompt="你是运维负责人。基于检测结果给出根因组件名。")
    dec.tools_spec, dec.tool_registry = [], {}
    txt = "\n".join(f"{c} -> {r}" for c, r in results) or "（无）"
    with contextlib.redirect_stdout(io.StringIO()):
        concl = dec.run(f"{PRIMARY}\n\n结果：\n{txt}\n\n根因组件名？只回答名称。", max_steps=1) or ""
    return concl


def arm_blackboard(root_comp, root_sys):
    """黑板：症状触发匹配专家（无中央）；专家只在自家子系统查。"""
    budget = Budget(BUDGET)
    tools = make_tools(root_comp, root_sys, budget)
    # 1) 症状先写入黑板（由「监控代理」自动触发，非中央调度）
    board = []
    board.append(("监控", tools["check_alerts"]()))
    board.append(("日志", tools["query_logs"]()))
    # 2) 黑板状态里出现子系统线索 → 对应专家被触发
    expert = Agent(system_prompt=(
        f"你是「{root_sys}」子系统专家。黑板显示异常指向你的子系统。"
        f"你只能在 {SUBSYS[root_sys]} 这些组件里逐个 inspect，定位根因组件名。"))
    expert.tools_spec, expert.tool_registry = SPEC[:1], {}
    # 手动驱动：让专家在预算内做 inspect
    expert.tools_spec = [SPEC[2]]
    expert.tool_registry = {"inspect": tools["inspect"]}
    with contextlib.redirect_stdout(io.StringIO()):
        concl = expert.run(f"{PRIMARY}\n\n【黑板】{board}\n\n请只在你的子系统内查，给出根因组件名。",
                           max_steps=BUDGET) or ""
    return concl


if __name__ == "__main__":
    n = int(os.getenv("BB_N", "6"))
    rng = random.Random(20261011)
    print(f"动作空间={len(ALL)} 组件  严格调用预算={BUDGET}")
    print(f"{'根因':<14}{'系统':<6}{'预排':<8}{'黑板':<8}")
    print("-" * 40)
    ph = bh = 0
    for i in range(n):
        root_comp = rng.choice([c for _, c in ALL])
        root_sys = next(s for s, cs in SUBSYS.items() if root_comp in cs)
        p = arm_preplanned(root_comp, root_sys)
        b = arm_blackboard(root_comp, root_sys)
        hp = root_comp in p; hb = root_comp in b
        ph += hp; bh += hb
        print(f"{root_comp:<14}{root_sys:<6}{('✅' if hp else '❌'):<8}{('✅' if hb else '❌'):<8}")
    print("-" * 40)
    print(f"正确率：预排 {ph}/{n} ｜ 黑板 {bh}/{n}")
