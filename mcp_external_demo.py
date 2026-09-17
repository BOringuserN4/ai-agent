# -*- coding: utf-8 -*-
"""
mcp_external_demo.py — 方案 B：接一个**别人写好的** MCP server

协议章 · 方案 B，2026/09/17。

方案 A 是「把自己的工具搬出去」（自己 → 别人）；
方案 B 是反方向（别人 → 自己）：直接插上一个第三方 server，
**一行适配代码都不写**，14 个文件操作工具就能用。

用的是官方 `@modelcontextprotocol/server-filesystem`（Node 写的）。

要量出三件事：
  1. **零适配的甜头**：我们写的适配代码是 0 行，工具却多了 14 个；
  2. **schema 膨胀的代价**：14 个工具的声明文本吃掉多少 token；
  3. **能不能真干活**：跑一个真实任务，看 Agent 能否用第三方工具完成。

用法：.venv/bin/python mcp_external_demo.py
"""
import json
import sys
import time
from pathlib import Path

from agent.core import Agent
from agent.mcp_bridge import MCPToolBridge, attach_mcp_tools

REPO_ROOT = str(Path(__file__).resolve().parent)
VENDOR_BIN = Path(REPO_ROOT) / "mcp_servers/vendor/node_modules/.bin/mcp-server-filesystem"
SANDBOX = "/tmp/mcp_sandbox"

QUESTION = (
    f"请读取 {SANDBOX}/notes.txt 的内容，告诉我里面有几行、每行分别是什么。"
    f"然后再读取 {SANDBOX}/readme.txt 的内容。"
)
SYSTEM = (
    "你是一个助手。需要读写文件时必须调用工具，不要凭猜测回答。"
    "拿到工具结果后，用中文简洁回答。"
)


def build_filesystem_bridge():
    """第三方 filesystem server 的桥接——**注意这里有多少适配代码**。"""
    bridge = MCPToolBridge(namespace="fs")   # 加前缀，避免与本地工具撞名
    bridge.add_server(
        "filesystem",
        str(VENDOR_BIN),
        [SANDBOX],                            # 只允许访问这个沙箱目录
    )
    return bridge


def main():
    print("=" * 64)
    print("🌐 方案 B：接第三方 MCP server（官方 filesystem，Node 写的）")
    print("=" * 64)
    print(f"   server：{VENDOR_BIN.relative_to(REPO_ROOT)}")
    print(f"   沙箱目录：{SANDBOX}")

    bridge = build_filesystem_bridge()
    bridge.start()
    try:
        names = bridge.tool_names
        print(f"\n✅ 一行适配代码没写，拿到 {len(names)} 个工具：")
        for n in names:
            print(f"   • {n}")

        # ---- 量 schema 体积 ----
        specs = bridge.to_openai_specs()
        spec_json = json.dumps(specs, ensure_ascii=False)
        print(f"\n📏 这 {len(names)} 个工具的 schema 总体积："
              f"{len(spec_json)} 字符（约 {len(spec_json)//2} token 的粗略量级）")

        # 逐个工具的 schema 体积排序，看谁最贵
        sized = sorted(
            ((len(json.dumps(s, ensure_ascii=False)), s["function"]["name"]) for s in specs),
            reverse=True,
        )
        print("   最贵的 5 个：")
        for chars, name in sized[:5]:
            print(f"     {name:<34} {chars:>5} 字符")

        # ---- 真干活：让 Agent 用第三方工具完成任务 ----
        print("\n" + "#" * 64)
        print("# 真实任务：读文件 + 数行数（全部用第三方工具完成）")
        print("#" * 64)
        a = Agent(system_prompt=SYSTEM, tools=None)
        a.tools_spec = []          # 清空本地工具，只用第三方
        a.tool_registry = {}
        attached = attach_mcp_tools(a, bridge)
        print(f"🔧 Agent 可用工具：{len(attached)} 个（全部来自第三方 server）")

        a.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        t0 = time.time()
        answer = a.run(QUESTION)
        elapsed = round(time.time() - t0, 2)
        used = [s.tool for s in a.tracer.steps if s.type == "tool_call"]

        print("\n" + "=" * 64)
        print("📊 结果")
        print("=" * 64)
        print(f"实际调用的第三方工具：{used}")
        print(f"token：{a.usage['total_tokens']}"
              f"（输入 {a.usage['prompt_tokens']} / 输出 {a.usage['completion_tokens']}）")
        print(f"耗时：{elapsed}s")
        print(f"\n回答：\n{answer}")

        print("\n💡 结论（对照方案 A）：")
        print("  · 甜头：适配代码 0 行，14 个工具直接可用——这就是 N+M 里的「+M」省掉了")
        print("  · 代价：schema 膨胀是真实的。方案 A（1 个工具）schema 才 291 字符，")
        print(f"          这里 14 个工具要 {len(spec_json)} 字符。**「不写适配」不等于「没有成本」**，")
        print("          成本从「写代码」转移到了「每轮都付的 token」上。")
        print("  · 风险：这些工具是别人写的，你看不到实现；描述文本与返回值都可能成为注入通道。")
        # ---- 锋利实验：同一任务，只暴露 1 个工具 vs 全部 14 个 ----
        print("\n" + "#" * 64)
        print("# 锋利实验：隔离「schema 膨胀」的纯成本")
        print("#" * 64)
        print("  同一道题、同一个答案，只改「暴露几个工具」")
        q2 = f"读取 {SANDBOX}/notes.txt 的内容并告诉我几行。"

        def run_with(keep, label):
            agent = Agent(system_prompt=SYSTEM, tools=None)
            agent.tools_spec = []
            agent.tool_registry = {}
            all_specs = bridge.to_openai_specs()
            all_reg = bridge.to_registry()
            agent.tools_spec = [s for s in all_specs
                                if s["function"]["name"] in keep]
            agent.tool_registry = {k: v for k, v in all_reg.items() if k in keep}
            chars = len(json.dumps(agent.tools_spec, ensure_ascii=False))
            agent.usage = {"prompt_tokens": 0, "completion_tokens": 0,
                           "total_tokens": 0}
            t0 = time.time()
            ans = agent.run(q2)
            el = round(time.time() - t0, 2)
            print(f"  【{label}】schema {chars} 字符 ｜ 总 {agent.usage['total_tokens']} token "
                  f"（输入 {agent.usage['prompt_tokens']}）｜ {el}s")
            return chars, agent.usage["total_tokens"], agent.usage["prompt_tokens"]

        c1, t1, p1 = run_with({"fs__read_text_file"}, "只暴露 1 个工具")
        c2, t2, p2 = run_with(set(names), f"暴露全部 {len(names)} 个")

        print(f"\n  ⚠️ 差异：schema {c2-c1:+d} 字符 ｜ 总 token {t2-t1:+d}"
              f"（输入 {p2-p1:+d}）")
        print(f"     任务完全一样，答案完全一样，**只因为它多带了 13 个用不到的工具**。")
        print(f"     多付 {(t2-t1)/max(t1,1)*100:.0f}% 的 token。")
        print("\n  👉 这就是「动态发现」的另一面：省了适配代码，"
              "但工具清单**每轮都在吃 token**。")
        print("     生产做法：工具裁剪/按需加载（只暴露当前任务相关的工具集），而不是全量挂载。")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
