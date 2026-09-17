# -*- coding: utf-8 -*-
"""
mcp_tool_pruning_demo.py — 工具裁剪：干掉「工具清单的租金」

协议章 · 工具裁剪，2026/09/17。

背景（方案 B 实测）：全量挂载 14 个第三方工具，同一任务、同一答案，
多付 **+3571 token（+308%）**。这钱花在工具清单本身，不是花在干活上。

本实验对比三种挂载策略，跑**同一道题**：
  甲 · 全量挂载（14 个）        —— 基线
  乙 · 规则裁剪（关键词命中）    —— 本节的解法
  丙 · 全量 + 简单套话（对照）    —— 验证「多挂工具」是否真的无益

要回答三个问题：
  1. 裁剪能省多少 token？（省了才是真的省）
  2. 裁剪后任务还做得对吗？（漏带工具 = 任务失败，比多带更贵）
  3. 裁剪的判据有没有花额外的钱？（规则是 0 token 的）

用法：.venv/bin/python mcp_tool_pruning_demo.py
"""
import json
import sys
import time
from pathlib import Path

from agent.core import Agent
from agent.mcp_bridge import MCPToolBridge
from agent.tool_selector import ToolSelector, attach_selected_tools

REPO_ROOT = str(Path(__file__).resolve().parent)
VENDOR_BIN = Path(REPO_ROOT) / "mcp_servers/vendor/node_modules/.bin/mcp-server-filesystem"
SANDBOX = "/tmp/mcp_sandbox"

SYSTEM = "你是一个助手。需要读写文件时必须调用工具，不要凭猜测回答。用中文简洁回答。"

# 多组任务：逼裁剪器同时命中「读」和「列」两类，检验会不会漏带
# (名称, 查询, 验收时答案里必须出现的关键词)
TASKS = [
    ("单组任务", f"读取 {SANDBOX}/notes.txt 的内容，告诉我里面有几行。",
     ["alpha", "beta", "gamma"]),
    ("多组任务", f"先列出 {SANDBOX} 目录下有哪些文件，再读取 notes.txt 的内容告诉我几行。",
     ["notes.txt", "alpha"]),
    # 压测发现的漏带 bug 回归用例：只含「目录」会命中 list 组，
    # 必须同时命中 write 组拿到 create_directory，否则任务直接失败。
    ("漏带回归", f"在 {SANDBOX} 里建一个叫 reports 的目录。",
     ["reports"]),
]

REPEATS = 3  # 单次 token/耗时抖动大，多跑取平均才敢下结论


def build_bridge():
    b = MCPToolBridge(namespace="fs")
    b.add_server("filesystem", str(VENDOR_BIN), [SANDBOX])
    return b


def run_case(bridge, label, query, mode, must_have):
    """mode: 'full' 全量 | 'pruned' 规则裁剪。跑 REPEATS 次取平均。"""
    tools_n = spec_chars = 0
    tokens, elapsed = [], []
    last_answer, used, ok_all = "", [], True

    for _ in range(REPEATS):
        a = Agent(system_prompt=SYSTEM, tools=None)
        a.tools_spec = []
        a.tool_registry = {}
        a.memory = None

        if mode == "full":
            from agent.mcp_bridge import attach_mcp_tools
            names = attach_mcp_tools(a, bridge)
        else:
            names, _ = attach_selected_tools(a, bridge, query, explain=False)

        tools_n = len(names)
        spec_chars = len(json.dumps(a.tools_spec, ensure_ascii=False))
        a.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        t0 = time.time()
        last_answer = a.run(query)
        elapsed.append(time.time() - t0)
        tokens.append(a.usage["total_tokens"])
        used = [s.tool for s in a.tracer.steps if s.type == "tool_call"]
        # 任务完成判据：答案里必须出现该任务的关键词
        if not all(k in last_answer for k in must_have):
            ok_all = False

    return {
        "label": label, "tools": tools_n, "spec_chars": spec_chars,
        "tokens": tokens, "avg_tokens": round(sum(tokens) / len(tokens)),
        "avg_elapsed": round(sum(elapsed) / len(elapsed), 2),
        "used": used, "answer": last_answer, "ok": ok_all,
    }


def main():
    bridge = build_bridge()
    bridge.start()
    try:
        total = len(bridge.tool_names)
        print("=" * 68)
        print(f"✂️  工具裁剪实验（可用工具共 {total} 个）")
        print("=" * 68)

        sel = ToolSelector()
        results = []
        for tname, query, must in TASKS:
            print(f"\n{'#' * 68}\n# {tname}：{query[:56]}…\n{'#' * 68}")
            sel.select(query, bridge.tool_names, explain=True)
            full = run_case(bridge, "全量挂载", query, "full", must)
            pruned = run_case(bridge, "规则裁剪", query, "pruned", must)
            results.append((tname, full, pruned))

            print(f"\n{'策略':<12}{'工具数':>7}{'schema':>10}{'平均token':>10}{'平均耗时':>10}")
            print("-" * 68)
            for r in (full, pruned):
                print(f"{r['label']:<12}{r['tools']:>7}{r['spec_chars']:>10}"
                      f"{r['avg_tokens']:>10}{str(r['avg_elapsed']) + 's':>10}")
            dt = pruned["avg_tokens"] - full["avg_tokens"]
            pct = dt / max(full["avg_tokens"], 1) * 100
            print("-" * 68)
            print(f"节省：{dt:+d} token（{pct:+.1f}%）")
            print(f"调用工具：全量 {full['used']}  裁剪 {pruned['used']}")
            print(f"任务完成：全量 {'✅' if full['ok'] else '❌'}  裁剪 {'✅' if pruned['ok'] else '❌'}")
            print(f"（各次 token：全量 {full['tokens']}｜裁剪 {pruned['tokens']}）")

        print("\n" + "=" * 68)
        print("📊 汇总")
        print("=" * 68)
        tot_f = tot_p = 0
        for tname, full, pruned in results:
            dt = pruned["avg_tokens"] - full["avg_tokens"]
            pct = dt / max(full["avg_tokens"], 1) * 100
            tot_f += full["avg_tokens"]
            tot_p += pruned["avg_tokens"]
            print(f"{tname}：全量 {full['tools']} 个 / {full['avg_tokens']} token"
                  f"  →  裁剪 {pruned['tools']} 个 / {pruned['avg_tokens']} token"
                  f"  （{dt:+d}, {pct:+.1f}%）")
        dt = tot_p - tot_f
        print(f"\n合计：{tot_f} → {tot_p} token（{dt:+d}, {dt/max(tot_f,1)*100:+.1f}%）")
        print("\n💡 结论：")
        print("  · 裁剪的收益不只是省 token——**工具少了，模型选错的概率也小**")
        print("  · 判据用规则、不用 LLM：省下来的钱不该被判断成本吃掉")
        print("  · 关键约束是「不能漏带」：漏掉必要工具 = 任务直接失败，比多带更贵")

        print("\n" + "=" * 68)
        print("🧪 边界压测（这些是规则法的真实弱点，必须盯住）")
        print("=" * 68)
        edge = [
            ("无关键词", "帮我处理一下 notes.txt"),
            ("复合动作", "先搜所有 txt，再把找到的第一个文件改个名"),
            ("纯闲聊", "你好，今天过得怎么样"),
        ]
        for name, q in edge:
            picked = sel.select(q, bridge.tool_names)
            print(f"  [{name}] {q}")
            print(f"     → {len(picked)}/{len(bridge.tool_names)}: {picked}")
        print("\n  ⚠️ 压测抓到的真 bug：「建一个叫 reports 的目录」原只命中 list 组，")
        print("     漏掉 create_directory → 任务直接失败。原因是 write 组关键词缺单字「建」。")
        print("     已修（回归用例：漏带回归）。**规则法的风险不在多选，在漏选。**")
        print("  💡 所以生产上要留两条后路：① 宁可回退全量的兜底；② 监控「选了但用不上」的比率。")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
