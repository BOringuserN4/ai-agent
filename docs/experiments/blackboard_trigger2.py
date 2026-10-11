# -*- coding: utf-8 -*-
"""Blackboard 专题 · 收官实验 v2（修正打分器 + 预算语义，2026/10/11）

本版修正两处缺陷：
  ① **打分器**：上一版 `root_comp in 结论` 会因「结论枚举了所有查过的组件」而假阳性
     （实测：es-search 未被查到却判 ✅）。→ 改为**精确解析最终宣告的根因**。
  ② **预算语义**：监控/日志是「自动喂到黑板上」的（不占诊断预算）；
     预算只封顶**昂贵的 inspect 调用**。

对照：
  · 预排臂：看到日志前盲定 3 次 inspect（不知哪个子系统）→ 命中率 ≈ 3/20
  · 黑板臂：日志指出子系统 → 在其 5 个组件内 inspect（≤3 次）→ 命中率 ≈ 3/5
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

PRIMARY = "order-api 今早开始报 500。请定位**根因组件**（20 个组件之一）。"
SPEC = [
    {"type": "function", "function": {"name": "check_alerts", "description": "查看告警",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "query_logs", "description": "查看错误日志",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "inspect", "description": "检查某组件（昂贵，有预算）",
        "parameters": {"type": "object", "properties": {"component": {"type": "string"}}, "required": ["component"]}}},
]


class InspectBudget:
    def __init__(self, n): self.left = n
    def take(self):
        if self.left <= 0: return False
        self.left -= 1; return True


def make_tools(root_comp, root_sys, budget):
    def check_alerts(): return "order-api: 500 错误率 12%（近 10 分钟）"
    def query_logs():   return f"order-api 错误日志：异常指向「{root_sys}」子系统"
    def inspect(component):
        if not budget.take():
            return "❌ 诊断预算已用尽，无法继续检查"
        c = (component or "").strip()
        return "❌ 确认异常（根因）" if c == root_comp else "✅ 正常"
    return {"check_alerts": check_alerts, "query_logs": query_logs, "inspect": inspect}


# ---- 精确打分：解析最终宣告的根因，而非子串包含 ----
ROOT_DECL = re.compile(r"根因(?:组件)?\s*[:：]?\s*\**\s*([a-z0-9][a-z0-9\-]{1,20})", re.I)
TAIL = re.compile(r"([a-z0-9][a-z0-9\-]{1,20})\s*$", re.I)


def declared_root(text):
    t = (text or "").strip()
    ms = ROOT_DECL.findall(t)
    if ms:
        return ms[0].lower()
    m = TAIL.search(t)
    return m.group(1).lower() if m else None


def score(text, root_comp):
    """只有当**最终宣告**的根因 == 真值 才算对（避免枚举假阳性）。"""
    return declared_root(text) == root_comp.lower()


def parse_calls(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m: return []
    try: return json.loads(m.group(0)).get("calls", [])
    except Exception: return []


def _safe_args(fn, args):
    import inspect as _i
    try:
        ok = set(_i.signature(fn).parameters)
    except Exception:
        return args or {}
    return {k: v for k, v in (args or {}).items() if k in ok}


def arm_preplanned(root_comp, root_sys):
    budget = InspectBudget(INSPECT_BUDGET)
    tools = make_tools(root_comp, root_sys, budget)
    planner = Agent(system_prompt=(
        "你是运维负责人。在**看到任何结果之前**，一次性决定最多 " + str(INSPECT_BUDGET) +
        " 次要 inspect 的组件（你**还不知道**是哪个子系统）。工具可先 check_alerts、query_logs。"
        "可选组件：" + ", ".join(c for _, c in ALL) +
        "。只输出 JSON {\"calls\":[{\"tool\":..,\"args\":{..}}]}。"))
    planner.tools_spec, planner.tool_registry = [], {}
    with contextlib.redirect_stdout(io.StringIO()):
        plan = planner.run(PRIMARY, max_steps=1) or ""
    calls = parse_calls(plan)
    # 先执行免费监控调用，再执行 inspect（受预算）
    feed = []
    for c in calls:
        if c.get("tool") in ("check_alerts", "query_logs"):
            feed.append(tools[c["tool"]]())
    inspects = [c for c in calls if c.get("tool") == "inspect"][:INSPECT_BUDGET]
    res = []
    for c in inspects:
        res.append((c["args"], tools["inspect"](**_safe_args(tools["inspect"], c.get("args")))))
    dec = Agent(system_prompt="你是运维负责人。基于结果给出**唯一的**根因组件，格式：根因组件：<名称>。")
    dec.tools_spec, dec.tool_registry = [], {}
    txt = ("日志：\n" + "\n".join(feed) + "\n检查：\n" +
           "\n".join(f"{a} -> {r}" for a, r in res)) if (feed or res) else "（无）"
    with contextlib.redirect_stdout(io.StringIO()):
        return dec.run(f"{PRIMARY}\n\n{txt}\n\n格式：根因组件：<名称>", max_steps=1) or ""


def arm_blackboard(root_comp, root_sys):
    budget = InspectBudget(INSPECT_BUDGET)
    tools = make_tools(root_comp, root_sys, budget)
    # 监控自动喂到黑板（不占诊断预算）
    board = [tools["check_alerts"](), tools["query_logs"]()]
    expert = Agent(system_prompt=(
        f"你是「{root_sys}」子系统专家。黑板已显示异常指向你的子系统。"
        f"你只能 inspect 这些组件：{'、'.join(SUBSYS[root_sys])}。"
        f"预算内逐个查，最后格式：根因组件：<名称>。"))
    expert.tools_spec, expert.tool_registry = [SPEC[2]], {"inspect": tools["inspect"]}
    with contextlib.redirect_stdout(io.StringIO()):
        return expert.run(f"{PRIMARY}\n\n【黑板】\n" + "\n".join(board) +
                          f"\n\n请在你的子系统内用 inspect 定位，格式：根因组件：<名称>",
                          max_steps=INSPECT_BUDGET) or ""


if __name__ == "__main__":
    n = int(os.getenv("BB_N", "6"))
    rng = random.Random(20261011)
    print(f"动作空间={len(ALL)} 组件  inspect 预算={INSPECT_BUDGET}（监控/日志免费）")
    print(f"{'根因':<14}{'系统':<6}{'预排':<8}{'黑板':<8}")
    print("-" * 40)
    ph = bh = 0
    for i in range(n):
        root_comp = rng.choice([c for _, c in ALL])
        root_sys = next(s for s, cs in SUBSYS.items() if root_comp in cs)
        p, b = arm_preplanned(root_comp, root_sys), arm_blackboard(root_comp, root_sys)
        hp, hb = score(p, root_comp), score(b, root_comp)
        ph += hp; bh += hb
        print(f"{root_comp:<14}{root_sys:<6}{('✅' if hp else '❌'):<8}{('✅' if hb else '❌'):<8}")
    print("-" * 40)
    print(f"正确率：预排 {ph}/{n} ｜ 黑板 {bh}/{n}（精确打分：只认最终宣告的根因）")
