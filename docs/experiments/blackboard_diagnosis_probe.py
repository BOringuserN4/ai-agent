# -*- coding: utf-8 -*-
"""Blackboard 专题 · 探针：故障诊断（2026/10/11）

场景（用户提出）：order-api 报 500 错误，诊断根因。
关键性质：**下一步查谁，取决于日志里发现了什么** —— 而日志内容**随机**（根因随机），
所以预排式无法靠先验蒙中。

两臂（同一模型、同一工具集，只差「控制流」）：
  · 预排臂（Pre-planned）：**看到任何结果之前**一次性列出完整调用序列 → 执行 → 汇总。
    （= 静态 workflow / 一次性 _plan 的真实形态）
  · 迭代臂（Blackboard 式）：看当前状态 → 决定下一步 → 再决定。

判定：根因是否正确 + 工具调用次数（浪费）+ token。
"""
import os, sys, io, json, random, re, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
import logging; logging.disable(logging.CRITICAL)
from agent.core import Agent

COMPONENTS = ["数据库", "缓存", "磁盘", "网络", "应用代码"]
SYMPTOM = {
    "数据库": "大量 ConnectionTimeout；连接池 active=50/50 已满",
    "缓存":   "Redis 命中率骤降至 40%，大量 cache miss",
    "磁盘":   "写入失败：No space left on device（/data 卷已满）",
    "网络":   "DNS 解析间歇失败；connection reset by peer",
    "应用代码": "NullPointerException at OrderService.java:142",
}
PRIMARY = "order-api 今天早上开始报 500 错误。请诊断出**根因是哪个组件**。"

SPEC = [
    {"type": "function", "function": {"name": "check_alerts", "description": "查看当前告警",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "query_logs", "description": "查看 order-api 最近错误日志",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "inspect", "description": "检查某个组件的状态",
        "parameters": {"type": "object", "properties": {"component": {"type": "string",
            "description": "组件名，取值：" + "/".join(COMPONENTS)}}, "required": ["component"]}}},
]


def build(root):
    def check_alerts():
        return "order-api: 500 错误率 12%（近 10 分钟）；其他服务无告警"
    def query_logs():
        return f"order-api 最近错误日志：{SYMPTOM[root]}"
    def inspect(component):
        c = (component or "").strip()
        return (f"{c} 检测：❌ 确认异常（根因）" if c == root
                else f"{c} 检测：✅ 正常")
    return {"check_alerts": check_alerts, "query_logs": query_logs, "inspect": inspect}


def parse_calls(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(0))
    except Exception:
        return []
    return d.get("calls", []) if isinstance(d, dict) else []


def arm_preplanned(root):
    """看到结果前一次性规划（静态 workflow）。"""
    tools = build(root)
    planner = Agent(system_prompt=(
        "你是运维负责人。你必须在**看到任何工具结果之前**，一次性列出完整的诊断调用序列。"
        "可用工具：check_alerts()、query_logs()、inspect(component)（component ∈ "
        + "/".join(COMPONENTS) + "）。只输出 JSON：{\"calls\":[{\"tool\":\"..\",\"args\":{..}}]}，不要解释。"))
    planner.tools_spec, planner.tool_registry = [], {}
    with contextlib.redirect_stdout(io.StringIO()):
        plan = planner.run(PRIMARY, max_steps=1) or ""
    calls = parse_calls(plan)
    results = []
    for c in calls:
        try:
            results.append((c, tools.get(c.get("tool"), lambda **k: "未知工具")(**c.get("args", {}))))
        except Exception as e:
            results.append((c, f"调用失败: {e}"))
    decider = Agent(system_prompt="你是运维负责人。基于检测结果给出根因。")
    decider.tools_spec, decider.tool_registry = [], {}
    txt = "\n".join(f"{c} -> {r}" for c, r in results) or "（无调用）"
    with contextlib.redirect_stdout(io.StringIO()):
        concl = decider.run(f"{PRIMARY}\n\n检测结果：\n{txt}\n\n根因是哪个组件？只回答组件名。",
                            max_steps=1) or ""
    tok = planner.usage["total_tokens"] + decider.usage["total_tokens"]
    return concl, len(calls), tok, calls


def arm_iterative(root):
    """迭代式（黑板式）：每步看状态再决定下一步。"""
    tools = build(root)
    a = Agent(system_prompt=(
        "你是运维负责人。你维护一块状态板：每调用一个工具，把结果记下，再决定下一步。"
        "信息足够时给出根因（只回答组件名）。"))
    a.tools_spec, a.tool_registry = SPEC, tools
    with contextlib.redirect_stdout(io.StringIO()):
        concl = a.run(PRIMARY, max_steps=8) or ""
    n = sum(1 for s in a.tracer.steps if s.type == "tool_call")
    return concl, n, a.usage["total_tokens"], None


def hit(text, root):
    return root in (text or "")


if __name__ == "__main__":
    n = int(os.getenv("BB_N", "4"))
    rng = random.Random(20261011)
    print(f"{'根因':<8}{'预排:正确':<10}{'预排:调用':<10}{'迭代:正确':<10}{'迭代:调用'}")
    print("-" * 56)
    ph = ih = pc = ic = 0
    for i in range(n):
        root = rng.choice(COMPONENTS)
        pc_, pcn, ptok, calls = arm_preplanned(root)
        ic_, icn, itok, _ = arm_iterative(root)
        ph += hit(pc_, root); ih += hit(ic_, root)
        pc += pcn; ic += icn
        print(f"{root:<8}{('✅' if hit(pc_,root) else '❌'):<10}{pcn:<10}"
              f"{('✅' if hit(ic_,root) else '❌'):<10}{icn}")
    print("-" * 56)
    print(f"正确率：预排 {ph}/{n} ｜ 迭代 {ih}/{n}")
    print(f"平均调用数：预排 {pc/n:.1f} ｜ 迭代 {ic/n:.1f}")
