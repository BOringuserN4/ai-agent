# AI Agent 从 0 到 1 开发项目

> 用 **DeepSeek + Python**，从零手写一个 **Multi-Agent** 系统。
> 本文档记录**项目架构、运行方式、核心原理**。项目已收敛为「多专家协作」的工程形态。

---

## 一、项目简介

这是一个**多 Agent（Multi-Agent）协作框架**，用最小依赖（`openai`）纯手写实现，不依赖 LangGraph/CrewAI 等框架——目的是**理解 Agent 的本质**。

核心架构：**Router（调度者）+ Worker（专家）**。
- 一个「调度者」判断用户意图；
- 多个「专家」各司其职、各有独立人格与工具集；
- 根据意图自动路由给对应专家处理。

---

## 二、环境与依赖

| 项 | 说明 |
|---|---|
| Python | 3.12+ |
| 依赖 | `openai`（连 DeepSeek）、`python-dotenv` |
| 模型 | DeepSeek `deepseek-chat`（V3） |
| API Key | 存于 `.env`（**已 gitignore，绝不入库**） |

### 安装
```bash
cd ai-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 填入 DEEPSEEK_API_KEY + DASHSCOPE_API_KEY
```

---

## 三、运行

### 命令行（统一入口）
```bash
python3 main.py
```
指令：
- 直接输入 → 与多 Agent 对话（自动路由）
- `/trace` → 查看本轮轨迹
- `/usage` → 查看 token 用量
- `/memory` → 查看长期记忆（跨会话）
- `/memory_extra` → 查看带标签+时间的记忆详情
- `/mem_clear` → 清空长期记忆
- `/clear` → 清空对话历史（不删长期记忆）
- `/exit` → 退出

### 示例
```bash
python3 main.py
你：帮我算 123 * 456        → 路由到「数学专家」
你：上海现在天气如何        → 路由到「天气专家」
你：给我讲个笑话            → 路由到「通用专家」
```

---

## 四、项目结构

```
ai-agent/
├── .env / .env.example   # 密钥（.env 已 gitignore）
├── .gitignore
├── requirements.txt
├── main.py               # 统一命令行入口
├── LICENSE               # MIT
├── README.md
└── agent/
    ├── __init__.py
    ├── core.py           # Agent 引擎（模型+工具+ReAct循环+上下文控制+记忆抽取接入）
    ├── tools.py          # 工具大本营（计算器/天气/时间）
    ├── tracing.py        # Tracer 追踪器（可观测性）
    ├── roles.py          # 多专家角色定义
    ├── multi_agent.py    # Multi-Agent 调度器（Router+Worker）
    ├── memory.py         # 长期记忆 RAG（DashScope 远程 embedding）
    └── extractor.py      # 记忆重要性过滤器（LLM 决策版）
```

---

## 五、核心原理

### 1. Agent 的本质
> **Agent 的智能 100% 来自 LLM，它自己不产智能。**
> Agent 用一个循环（ReAct），把「一段持续生效的 **prompt**（角色）+ 可装载的**记忆**（上下文）+ 一批**工具**（执行手臂）」与 LLM 的决策能力装配起来。

| 角色 | 干什么 |
|---|---|
| LLM（大脑） | 读懂 → 决策（选工具）→ 翻译（写参数） |
| 工具（手臂） | **真正执行**（计算/查天气/…） |
| function call（神经） | 连接 LLM 决策与工具执行 |
| prompt（剧本设定） | 全程驻留上下文的角色约束 |
| 记忆（上下文） | 短期=history 整段喂入；长期=外部库检索 |

### 2. ReAct 循环
> 思考（Reason）→ 决定行动（Act）→ 观察结果（Observe）→ 再思考，循环到完成。`max_steps` 兜底防死循环。

### 3. 记忆机制
- **短期记忆**：`self.history` 列表，每轮把整个历史再喂给模型（LLM 自身无记忆）。
- **长期记忆**：外部存储 + 远程 embedding（阿里云 DashScope `text-embedding-v3`），通过检索（RAG）调回相关片段。
- **上下文预算**：`trim_history()` 抹旧保新，防 token 爆炸。
- **智能抽取**（`extractor.py`）：回答后调一次轻量 LLM，让模型决定本轮对话是否值得记，输出结构化 JSON（`keep/text/tags`）。从「无脑存」升级为「只存高价值」。决策原则：明确偏好/个人信息/跨会话事实才记；问候、寒暄、一次性计算不记。

### 4. 可观测性
> Tracer 记录每一步「思考/工具调用/工具结果/回答」+ 耗时 + token——多 Agent 调试与可视化的基础。

### 6. Multi-Agent 架构
> **Router**（调度者，只决策）输出 `{"expert":"..."}`，**Worker**（专家，各自人格+工具）执行，汇总回传。

### 7. 智能记忆抽取（LLM 决策）
> 与其写一堆 if/正则 判断「什么值得记」，不如让 LLM 自己做。
> 决策类调用用 `temperature=0 + max_tokens=200` 控制成本与稳定性，容错兑底为不记。
> **设计原则**：凡涉及「语义判断」的决策，优先让 LLM 做；硬编码规则难覆盖、难泛化。

---

## 六、安全红线

1. `.env` 已 `gitignore`，密钥绝不入库。
2. 计算器用 `eval` 仅限个人演示，**生产严禁**。
3. 高风险操作（删/发/改/钱/重启/批量）必须人机审批。

---

## 七、演进方向

- ~~长期记忆（向量库 RAG）~~ ✅ 已完成（DashScope 远程 embedding）
- ~~智能记忆抽取（LLM 过滤）~~ ✅ 已完成（extractor.py）
- 真实工具（web 搜索 / 读网页 / 接数据库）
- MCP 工具生态
- 更复杂编排（Pipeline / 层级 / Debate）
- 可视化界面（金銮殿等）

---

*从 0 到 1 · 2026-09-06 起步，2026-09-07 收敛为 Multi-Agent 工程形态。*
