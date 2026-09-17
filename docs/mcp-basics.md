# 协议章 · MCP 基础

> 把本项目自己的天气工具「适配」成一个 MCP server，让 Agent 用上它，
> 并量出「协议层」的真实价格。方案 A：把自己写的工具搬出去。
> 完成日期：2026/09/17。

---

## 1. 是什么

**MCP（Model Context Protocol）= 工具与 Agent 之间的通用插座。**

一句话对比：现在你的工具是**焊死在这个项目里**的；MCP 之后，工具变成一个
**独立进程**，任何支持 MCP 的客户端都能插上用。

| | 以前（Function Calling） | 现在（MCP） |
|---|---|---|
| 工具在哪 | 项目里的一个 Python 函数 | **独立进程**（可以是 Node/Go/别的语言） |
| 清单从哪来 | 代码里**手写**声明 | 运行时向 server **动态问**出来 |
| 换客户端 | 重写一份适配 | 不用改，插上就用 |

---

## 2. 结构定位

### 三个角色

| 角色 | 是什么 | 本项目对应 |
|---|---|---|
| **Host** | 跑 Agent、发起请求的那一方 | `main.py` / Agent |
| **Client** | Host 内部负责说协议话的连接器 | `agent/mcp_bridge.py` |
| **Server** | 提供能力的**独立进程** | `mcp_servers/weather_server.py` |

传输走 **stdio**（标准输入输出）——server 是 client 拉起的子进程，
**客户端退出，server 被回收**。

### 三种原语（比 Function Calling 更宽）

| 原语 | 谁发起 | 干什么 |
|---|---|---|
| **Tools** | 模型 | 执行动作（会改状态） |
| **Resources** | 应用 | 读数据（只读） |
| **Prompts** | 用户 | 预置提示词模板 |

本项目的 Function Calling 只覆盖了 **Tools** 一种。本次也只演示 Tools。

---

## 3. 为什么这么设计

**要解决的是 N×M 问题。**

```
N 个 Agent 框架 × M 个工具 = N×M 份适配
```

每换一个框架，所有工具都要重写一遍适配层。MCP 把适配压成 **N+M**：
**框架实现一次 client，工具实现一次 server**，之后任意组合。

> 类比：以前每台电器配一种插座（N×M 个转接头）；MCP 是 USB-C，
> 插座和电器各自实现一次协议，随便插。

### 一个关键的设计取舍：适配 ≠ 重写

`mcp_servers/weather_server.py` **没有重写**天气逻辑，而是复用了
`agent.tools.get_weather`。

原因：「适配」的语义是给已有能力**套一层协议外壳**，不是重新实现一遍。
**真正的解耦发生在接口层（进程边界 + 协议），不在实现层。**
等这个 server 将来被抽成独立仓库/包时，再把函数一起搬走即可。

---

## 4. 代价（值钱那行）

MCP 不是免费的。实测拆成三笔账：

| 代价项 | 实测值 | 说明 |
|---|---|---|
| **描述文本吃 token** | **+36 字符 / +21 token**（每个工具） | 动态发现带回的 schema 更啰嗦 |
| **协议层往返** | **0.69 ms** | 跨进程调用 vs 本地函数直调 |
| **冷启动** | **≈500 ms** | 拉起子进程 + 握手 + `list_tools` |

**三条结论（都反直觉）：**

1. **token 是会涨的，不是会省**。MCP 自动生成的 JSON Schema 带 `title` 等
   额外元数据，比手写声明更啰嗦。凭「协议更先进」就以为更省 token 是错的。
2. **协议往返便宜到可以忽略**（0.69 ms）。相比一次 LLM 调用（约 1 秒）、
   一次联网查询（约 1.2 秒），0.69 ms 是噪声。**「协议层很贵」是错觉。**
3. **真正的新开销在别处**：
   - **运维复杂度**：多一个子进程要管（生命周期、崩溃恢复、日志）；
   - **冷启动 500 ms**：每次拉起都要付出；
   - **动态发现的双刃剑**：清单不在你代码里了 → 灵活，但也**不可控**
     （server 改了什么你事前不知道）；
   - **安全面变大**：工具描述/返回值本身成为**注入通道**（第三方 server 尤其危险）。

**一句话**：MCP 买的不是「省钱」，是「**一次实现、处处可用**」。
钱花在运维和可发现性上，省在重复适配上。

---

## 5. 代码在哪

| 文件 | 角色 | 说明 |
|---|---|---|
| `mcp_servers/weather_server.py` | **Server** | 把 `get_weather` + `ping` 暴露为 MCP 工具 |
| `mcp_client_weather.py` | **Client（最小）** | 独立验证脚本：握手 → `tools/list` → `tools/call` |
| `agent/mcp_bridge.py` | **Client（生产形态）** | 把 MCP 工具桥接进同步 Agent |
| `mcp_agent_demo.py` | **对照实验** | 本地工具 vs MCP 工具 |

### 异步 / 同步的桥接（本项目的关键实现）

MCP 客户端是**异步**的，本项目的 Agent 是**同步**的，硬凑会打架。

解法：把 MCP 的 asyncio 事件循环放到**后台线程**常驻，
主线程用 `asyncio.run_coroutine_threadsafe` 把调用投递过去——

```python
fut = asyncio.run_coroutine_threadsafe(self._call_async(name, args), self._loop)
return fut.result(timeout=timeout)
```

于是对 Agent 而言，**MCP 工具跟本地工具一样是个同步函数**。

### 为什么不改 core.py

Agent 已暴露 `tools_spec` / `tool_registry`，`attach_mcp_tools()` 直接**追加**，
MCP 工具就与本地工具共存。协议层的引入是「**外挂式**」的，
符合本项目「新能力尽量不侵入旧代码」的习惯。

---

## 6. 怎么跑

```bash
# ① 最小客户端：看协议本身（不接 Agent）
.venv/bin/python mcp_client_weather.py 上海

# ② 对照实验：本地工具 vs MCP 工具
.venv/bin/python mcp_agent_demo.py
```

`mcp_client_weather.py` 的输出会依次显示：
握手信息 → `tools/list` 发现的工具清单（**注意：这份清单不在客户端代码里**）
→ `tools/call` 的实际返回。

---

## 7. 实测账（2026/09/17）

### 对照实验：同一问题「杭州现在天气怎么样？」

工具集严格对齐（两组都只有 **1 个** get_weather 工具），各跑 3 次取平均：

| 组别 | 工具来源 | schema 字符 | 平均 token | 平均耗时 |
|---|---|---|---|---|
| 甲组 · 本地 | 手写声明 | 255 | **900** | 3.23s |
| 乙组 · MCP | 动态发现 | 291 | **921** | 2.90s |
| 差值 | | **+36** | **+21**（+2.3%） | −0.33s（噪声） |

结论：**答案质量一致，token 略涨，耗时无差异**。

### 协议层开销（用不联网的 `ping` 工具隔离测量，各 20 次取中位）

| 调用方式 | 中位耗时 |
|---|---|
| 本地函数直调 | ~0.000 ms |
| MCP 跨进程调用 | **0.69 ms** |

### 冷启动（拉到可用，测 3 次）

| 阶段 | 耗时 |
|---|---|
| 拉起子进程 + initialize 握手 + `list_tools` | **≈500 ms** |

---

## 8. 踩过的坑（mcp 1.x → 2.x 的 API 变更）

本次用的是 `mcp 2.2.0`，与网上大量 1.x 教程**不兼容**：

| 1.x 写法 | 2.x 实际 |
|---|---|
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer`（FastMCP 已改名） |
| `info.serverInfo` | `info.server_info`（字段改 snake_case） |
| `info.protocolVersion` | `info.protocol_version` |
| `tool.inputSchema` | `tool.input_schema` |

**教训**：装完包先跑一遍 `dir()` / `inspect.signature()` 确认真实 API，
**别照抄教程**。本次就是因为直接照 1.x 写法写，连撞两次 `AttributeError`。

### 另一个坑：工具名撞车

MCP 工具也叫 `get_weather`，挂载时**覆盖**了本地同名工具
（`{**local_registry, **mcp_registry}`）。

本 demo 里两者行为一致所以无害，但**生产环境必须处理**：
给 MCP 工具加命名空间前缀（如 `weather__get_weather`），否则
「本地同名工具被静默替换」这种 bug 极难排查。

---

## 9. 下一步

- **方案 B**：接一个**别人写好的** MCP server（如官方 filesystem），
  体会「别人的工具我能直接插进来用」——本次只做了自己的工具搬出去。
- **命名空间**：为 MCP 工具加前缀，解决上面的撞车问题。
- **Resources / Prompts**：本次只用了 Tools，另两种原语未碰。
