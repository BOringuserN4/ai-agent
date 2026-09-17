# -*- coding: utf-8 -*-
"""
agent/mcp_bridge.py — 把 MCP server 的工具「桥接」进同步的 Agent

协议章 · 第三步，2026/09/17。

要解决的矛盾：
  - MCP 客户端是**异步**的（asyncio + stdio 长连接）；
  - 本项目的 Agent 是**同步**的（openai 同步 SDK + for 循环）。

  两者硬凑在一起会打架：不能在同步循环里 await。

解法（本项目采用）：
  把 MCP 的 asyncio 事件循环放到**后台线程**里常驻，
  主线程通过 `asyncio.run_coroutine_threadsafe` 把调用「投递」过去并等结果。
  于是对 Agent 而言，MCP 工具跟本地工具一样是「一个同步函数」。

代价（值钱那行）：
  - 多一个常驻线程 + 一次跨线程调度；
  - 每次调用都有一次「投递-等待」的往返，比本地函数直接调用慢；
  - server 进程是子进程，**它的生命周期绑在客户端上**（客户端退出，server 被回收）。

为什么不改 core.py：
  Agent 已经暴露了 tools_spec / tool_registry 两个属性，
  attach_mcp_tools() 直接往这两个上面**追加**，就能让 MCP 工具与本地工具共存。
  这样协议层的引入是「外挂式」的——符合本项目「新能力尽量不侵入旧代码」的习惯。
"""
import asyncio
import threading
from contextlib import AsyncExitStack

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


class MCPToolBridge:
    """管理一个或多个 MCP server 的连接，并把它们的工具暴露给 Agent。

    用法：
        bridge = MCPToolBridge()
        bridge.add_weather_server()   # 或 add_server(name, command, args)
        bridge.start()                # 拉起后台事件循环 + 握手 + 拉工具清单
        attach_mcp_tools(agent, bridge)
        ... 正常使用 agent ...
        bridge.stop()
    """

    def __init__(self, namespace: str = None):
        """
        Args:
            namespace: 可选命名空间前缀。传入 "fs" 时，工具对外暴露为
                `fs__read_file`，避免与本地同名工具**静默互相覆盖**。
                方案 A 实测过的坑：`{**local, **mcp}` 会让 MCP 工具悄悄顶掉
                本地同名工具，排查起来极难。生产必须加前缀。
        """
        self.namespace = namespace
        self._servers = []          # [(name, StdioServerParameters)]
        self._tools = []            # 从 server 动态发现的工具（原始 MCP Tool 对象）
        self._tool_to_server = {}   # 对外工具名 -> server 名
        self._exposed_to_original = {}  # 对外工具名 -> server 上的原名
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._session_by_server = {}  # server 名 -> ClientSession
        self._error = None

    # ---- 注册 server ----
    def add_server(self, name: str, command: str, args: list):
        """注册一个 stdio MCP server。"""
        self._servers.append((name, StdioServerParameters(command=command, args=args)))

    # ---- 启动（同步接口，内部拉起后台事件循环）----
    def start(self, timeout: float = 30.0):
        """启动后台事件循环，握手所有 server，拉取工具清单。阻塞直到就绪。"""
        if not self._servers:
            raise ValueError("请先用 add_server() 注册至少一个 MCP server")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout):
            raise TimeoutError("MCP bridge 启动超时")
        if self._error:
            raise self._error
        return self

    def _run_loop(self):
        """后台线程入口：建事件循环，常驻直到 stop()。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:          # 启动阶段失败要能被主线程看到
            self._error = e
            self._ready.set()
        finally:
            self._loop.close()

    async def _serve(self):
        """在同一个 AsyncExitStack 里维持所有 server 连接（长连接不能中途退出）。"""
        async with AsyncExitStack() as stack:
            try:
                for name, params in self._servers:
                    read, write = await stack.enter_async_context(stdio_client(params))
                    session = await stack.enter_async_context(ClientSession(read, write))
                    info = await session.initialize()
                    self._session_by_server[name] = session
                    si = getattr(info, "server_info", None)
                    print(f"   🔌 MCP 已连接 [{name}]：{si.name} v{si.version}")

                    listed = await session.list_tools()
                    for t in (getattr(listed, "tools", []) or []):
                        exposed = f"{self.namespace}__{t.name}" if self.namespace else t.name
                        self._tools.append(t)
                        self._tool_to_server[exposed] = name
                        self._exposed_to_original[exposed] = t.name
                print(f"   📋 MCP 共发现 {len(self._tools)} 个工具："
                      f"{[t.name for t in self._tools]}")
            except Exception as e:
                self._error = e
                self._ready.set()
                return

            self._ready.set()
            # 常驻：直到主线程叫停
            while not self._stop.is_set():
                await asyncio.sleep(0.05)

    # ---- 同步调用接口 ----
    def to_openai_specs(self) -> list:
        """把 MCP 工具清单翻译成 OpenAI function-calling 的 tools 规范。

        这里就是 N+M 的落点：不管 server 是 Python/Node/Go 写的，
        只要它说 MCP，翻译出的 schema 形状都一样。
        """
        specs = []
        for t in self._tools:
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {}
            exposed = f"{self.namespace}__{t.name}" if self.namespace else t.name
            specs.append({
                "type": "function",
                "function": {
                    "name": exposed,
                    "description": t.description or "",
                    "parameters": schema or {"type": "object", "properties": {}},
                },
            })
        return specs

    def call(self, name: str, arguments: dict = None, timeout: float = 30.0) -> str:
        """同步调用一个 MCP 工具（跨线程投递到后台事件循环）。"""
        if name not in self._tool_to_server:
            return f"❌ MCP 没有名为 {name} 的工具"
        fut = asyncio.run_coroutine_threadsafe(
            self._call_async(name, arguments), self._loop
        )
        try:
            return fut.result(timeout=timeout)
        except Exception as e:
            return f"❌ MCP 调用失败：{type(e).__name__}: {e}"

    async def _call_async(self, name: str, arguments: dict) -> str:
        server_name = self._tool_to_server[name]
        session = self._session_by_server[server_name]
        original = self._exposed_to_original.get(name, name)
        result = await session.call_tool(original, arguments or {})
        parts = [getattr(i, "text", "") for i in (getattr(result, "content", None) or [])]
        text = "\n".join(p for p in parts if p)
        if getattr(result, "isError", None):
            return f"❌ {text}"
        return text or "（无文本内容）"

    def to_registry(self) -> dict:
        """工具名 -> 可调用函数，供 Agent 的 tool_registry 使用。"""
        return {
            (f"{self.namespace}__{t.name}" if self.namespace else t.name):
                (lambda _n=(f"{self.namespace}__{t.name}" if self.namespace else t.name), **kw:
                 self.call(_n, kw))
            for t in self._tools
        }

    @property
    def tool_names(self) -> list:
        if self.namespace:
            return [f"{self.namespace}__{t.name}" for t in self._tools]
        return [t.name for t in self._tools]

    def stop(self):
        """关闭后台循环与所有 server 连接。"""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)


def attach_mcp_tools(agent, bridge: MCPToolBridge):
    """把 bridge 发现的 MCP 工具挂到一个已存在的 Agent 上。

    只在 agent 的 tools_spec / tool_registry 上追加，不改 core.py。
    返回挂上去的工具名列表。
    """
    agent.tools_spec = list(agent.tools_spec) + bridge.to_openai_specs()
    agent.tool_registry = {**agent.tool_registry, **bridge.to_registry()}
    return bridge.tool_names


def build_weather_bridge(repo_root) -> MCPToolBridge:
    """便捷函数：拉起本项目的 weather MCP server。"""
    import sys
    from pathlib import Path
    server = Path(repo_root) / "mcp_servers" / "weather_server.py"
    bridge = MCPToolBridge(namespace="weather")
    bridge.add_server("weather", sys.executable, [str(server)])
    return bridge
