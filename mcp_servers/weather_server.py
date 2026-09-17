# -*- coding: utf-8 -*-
"""
mcp_servers/weather_server.py — 把本项目的天气工具「适配」成一个 MCP server

协议章 · 第一步（方案 A：把自己写的工具搬出去），2026/09/17。

结构定位（MCP 三角色）：
  - Host   = 跑 Agent 的那一方（main.py / 本项目）
  - Client = Host 内部负责说协议话的连接器（下一步写）
  - Server = **本文件**，一个独立进程，通过 stdio 提供能力

它证明了什么：
  同一个 get_weather 实现，包一层协议之后，**任何**支持 MCP 的客户端
  （Claude Desktop、IDE、别的 Agent 框架）都能直接调用，
  不需要为每个客户端重写一份适配。这就是 N×M → N+M 的落点。

一个设计取舍（值得记住）：
  这里**没有重写**天气逻辑，而是从 agent.tools 复用 get_weather。
  原因：「适配」的语义是给已有能力套协议外壳，不是重新实现一遍。
  真正的解耦发生在**接口层**（进程边界 + 协议），不在实现层。
  等这个 server 将来被抽成独立仓库/包，再把函数一起搬走即可。

运行方式（stdio，由客户端拉起）：
    .venv/bin/python mcp_servers/weather_server.py
自测（不接 Agent，先用官方工具看能不能列出/调用）：见 mcp_client_weather.py
"""
import os
import sys

# 让「独立进程」也能找到项目模块（server 被客户端以任意 cwd 拉起时也成立）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.mcpserver import MCPServer  # mcp>=2：即旧版 FastMCP

from agent.tools import get_weather


server = MCPServer(
    name="weather-server",
    title="天气查询 MCP Server",
    instructions="提供中文城市天气查询。支持的演示城市：北京/上海/广州/深圳/杭州/成都。",
    version="0.1.0",
)


@server.tool(
    name="get_weather",
    title="查询城市天气",
    description=(
        "查询指定城市的当前天气（气温、天气描述、风速）。"
        "支持的城市：北京、上海、广州、深圳、杭州、成都（中文名或拼音均可）。"
    ),
)
def get_weather_tool(city: str) -> str:
    """查询指定城市的当前天气。

    Args:
        city: 城市中文名或拼音，如 '北京'、'Shanghai'、'Guangzhou'。
    """
    return get_weather(city)


@server.tool(
    name="ping",
    title="健康检查",
    description="返回 pong。用于确认 server 存活、以及测量协议层往返开销（不走网络）。",
)
def ping_tool() -> str:
    """返回 pong（纯本地，用于健康检查与协议开销测量）。"""
    return "pong"


if __name__ == "__main__":
    server.run(transport="stdio")
