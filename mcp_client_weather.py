# -*- coding: utf-8 -*-
"""
mcp_client_weather.py — 最小 MCP 客户端，验证 weather MCP server

协议章 · 第二步，2026/09/17。

它做三件事（也是 MCP 客户端最小闭环）：
  1. 拉起 server 进程（stdio），完成 initialize 握手；
  2. tools/list —— **动态发现** server 有哪些工具（注意：清单不在我代码里）；
  3. tools/call —— 实际调用一次，拿到结果。

为什么这步重要：
  你项目里现有的工具清单是**手写**在 agent/tools.py 里的（get_tools_spec）。
  MCP 后，工具清单变成**运行时从 server 问出来**的——
  这就是「动态发现」，也是 MCP 既省适配、又引入新代价（描述文本吃 token）的源头。

用法：.venv/bin/python mcp_client_weather.py [城市]
"""
import asyncio
import sys
from pathlib import Path

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = REPO_ROOT / "mcp_servers" / "weather_server.py"


def _text_of(result) -> str:
    """把 CallToolResult 里的文本内容拼出来（MCP 返回的是内容块数组）。"""
    parts = []
    for item in (getattr(result, "content", None) or []):
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "（无文本内容）"


async def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "上海"

    params = StdioServerParameters(
        command=sys.executable,          # 用当前 venv 的解释器
        args=[str(SERVER_SCRIPT)],
        env=None,
    )

    print("=" * 58)
    print("🔌 MCP 客户端启动（stdio）")
    print("=" * 58)
    print(f"   拉起 server：{SERVER_SCRIPT.name}")

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            si = getattr(info, "server_info", None) or getattr(info, "serverInfo", None)
            print(f"   ✅ 握手完成：{si.name} v{si.version}")
            print(f"   协议版本：{getattr(info, 'protocol_version', None) or getattr(info, 'protocolVersion', '?')}")

            # ---- tools/list：动态发现 ----
            listed = await session.list_tools()
            tools = getattr(listed, "tools", []) or []
            print(f"\n📋 tools/list → 发现 {len(tools)} 个工具（清单来自 server，不在客户端代码里）：")
            for t in tools:
                schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {}
                props = list((schema.get("properties") or {}).keys())
                required = schema.get("required") or []
                print(f"   • {t.name}")
                print(f"     描述：{(t.description or '').strip()[:80]}")
                print(f"     入参：{props}（必填 {required}）")

            # ---- tools/call：实际调用 ----
            print(f"\n🛠️  tools/call → get_weather(city={city!r})")
            result = await session.call_tool("get_weather", {"city": city})
            print(f"   isError = {getattr(result, 'isError', None)}")
            print(f"   ── 返回 ──")
            print(f"   {_text_of(result)}")

    print("\n" + "=" * 58)
    print("🏁 客户端退出，server 进程随之关闭（stdio 生命周期 = 客户端生命周期）")
    print("=" * 58)


if __name__ == "__main__":
    asyncio.run(main())
