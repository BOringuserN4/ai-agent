# AI Agent 从 0 到 1：一个可读、可跑、可评测的白盒 Agent

> 用 **Python + DeepSeek**，从 **88 行**手写到一个多 Agent 系统。
> 不依赖 LangGraph / CrewAI；每加一个结构，都配代码、实测和边界。
>
> **这本书还在写**：单文件初稿在
> [`docs/书/Agent入门-初稿.md`](docs/书/Agent入门-初稿.md)，
> 全书目录在 [`docs/README.md`](docs/README.md)。

---

## 一、先看什么

| 你想 | 去哪 |
|---|---|
| **30 秒看 Agent 本质** | `.venv/bin/python minimal.py "帮我算 123 * 456"` |
| **看一次 Agent 回放** | [`visualizer/index.html`](visualizer/index.html)（P1/P2 时序/结构切换：开发小工具 / 记忆 / 最小，直接打开） |
| **从头读这本书** | [`docs/书/Agent入门-初稿.md`](docs/书/Agent入门-初稿.md) |
| **查全书目录** | [`docs/README.md`](docs/README.md) |
| **看编辑主线/章节因果链** | [`docs/00-索引/全书目录与主线.md`](docs/00-索引/全书目录与主线.md) |
| **看全书覆盖评估/改进清单** | [`docs/00-索引/全书覆盖评估与改进清单.md`](docs/00-索引/全书覆盖评估与改进清单.md) |
| **看架构图** | [`docs/05-收尾章/架构.md`](docs/05-收尾章/架构.md) |
| **看踩过的坑** | [`docs/00-索引/问题清单.md`](docs/00-索引/问题清单.md) |
| **看 DSH 技术研究** | [`docs/07-DSH研究/DSH技术设计与实现.md`](docs/07-DSH研究/DSH技术设计与实现.md) |
| **看按日期的复盘** | [`docs/08-日志/项目日志-2026.md`](docs/08-日志/项目日志-2026.md) |

> **读法**：第一次读，从初稿的序章开始，按“篇”顺序走；
> 复习时只看每讲开头的“前情/本章只回答”和结尾的“代价/下一章为什么存在”。

---

## 二、这是什么 / 不是什么

**是**：

- 一个**纯 Python 手写**的 Agent 教学项目：21 个业务模块，约 4800 行；
- 一条**能力阶梯**：`minimal.py` 88 行 → 完整多 Agent 系统；
- 一套**可复现的实验账**：记忆、编排、成本、EC、MCP 都有实测数字和边界；
- 一本**正在写的书**：把讲义按“为什么需要它 → 怎么工作 → 付什么代价”串起来。

**不是**：

- 不是生产级框架，不承诺 SLA、并发、权限隔离；
- 不是 benchmark，评测样本小（n 小），结论只对本项目/本模型负责；
- 不是“多 Agent 一定更强”的宣传；相反，**多 Agent 是成本结构**。

---

## 三、快速开始

### 环境

- Python 3.12+
- 依赖：`openai`、`python-dotenv`、`chromadb`、`numpy`、`langfuse`、`mcp`

```bash
cd ai-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 在 .env 填 DEEPSEEK_API_KEY / DASHSCOPE_API_KEY；.env 已被 gitignore
```

### 30 秒看本质

```bash
.venv/bin/python minimal.py "帮我算 123 * 456"
```

`minimal.py` 只有 88 行纯代码：一个 ReAct 循环 + 一份工具清单。
先读它，再读完整版，不会被 21 个模块淹没。

### 完整入口

```bash
.venv/bin/python main.py
```

| 指令 | 作用 |
|---|---|
| 直接输入 | 与多 Agent 对话（自动路由） |
| `/trace` | 查看本轮轨迹 |
| `/usage` | 查看 token 用量 |
| `/memory` | 查看长期记忆 |
| `/json <schema> <问题>` | 结构化 JSON 输出 |
| `/pipe <场景> <问题>` | Pipeline 模式 |
| `/clear` / `/exit` | 清空会话 / 退出 |

模型默认 `deepseek-flash`；可在 `.env` 里改。

---

## 四、项目结构（当前）

```text
ai-agent/
├── minimal.py                 # 阶梯 0：88 行最小 Agent
├── main.py                    # 完整命令行入口
├── agent/                     # 21 个业务模块
│   ├── core.py                # ReAct 循环 + 上下文 + 记忆接入
│   ├── tools.py               # 工具大本营
│   ├── roles.py               # 专家角色
│   ├── multi_agent.py         # Router + Worker
│   ├── memory.py              # ChromaDB + embedding + 阈值
│   ├── extractor.py           # 记忆写侧过滤
│   ├── pipeline.py            # Pipeline
│   ├── evaluator_critic.py    # EC
│   ├── group_chat.py          # Group Chat
│   ├── contract_net.py        # Contract Net
│   ├── debate.py              # Debate
│   ├── mcp_bridge.py          # MCP 桥接
│   ├── observation.py         # {ok,data,error} 感知契约
│   ├── events.py              # 事件层：EventBus + JSONL trace
│   └── ...                    # json_mode / rerank / tool_selector / tracing ...
├── eval_*.py                  # 评测与对照实验
├── visualizer/                # Agent 回放 demo（P1）
├── mcp_servers/               # MCP server
├── scripts/                   # 本地推理/连通性脚本
├── langfuse/                  # Langfuse 自部署（可选）
├── docs/
│   ├── 书/Agent入门-初稿.md    # 单文件初稿（先读这个）
│   ├── README.md              # 全书目录
│   ├── 00-索引/               # 书前/附录：教学总览、学习总结、问题清单...
│   ├── 01-基础章/             # 模型 → 最小 Agent → 感知 → 上下文
│   ├── 02-编排章/             # Router/Pipeline/Fan-out/EC/高级结构
│   ├── 03-实战章/             # 记忆、本地小模型、约束
│   ├── 04-协议章/             # MCP
│   ├── 05-收尾章/             # 架构
│   ├── 06-可视化/             # 交互可视化设计
│   ├── 07-DSH研究/            # DSH 技术研究与可吸收路线
│   ├── 08-日志/               # 按日期的复盘/审视/重构
│   └── 99-番外/               # 模型能力、本地推理
└── README.md
```

> `docs/README.md` 是“书”的目录；`docs/书/` 是单文件初稿；
> `00-索引/` 只放书前/附录；按日期的内容统一在 `08-日志/`。

---

## 五、核心原理（五句话）

1. **模型只会“说”**：它读一叠 messages，写下一段文字；不记得你，也不会替你动手。
2. **Agent = 模型 + 循环 + 工具清单 + 一点状态**；`minimal.py` 就是这四样东西的最小实现。
3. **记忆 = 写侧 + 读侧**：回答后决定记什么，提问前按意思召回；会忘和会记一样重要。
4. **多 Agent 是成本结构**：每拆一个就多一份交接、上下文和 token；只有“单 Agent 做不到”才值得拆。
5. **监控不等于评测**：监控答“发生了什么”，评测答“对不对”；EC 需要外部独立信号。

---

## 六、已实现 / 当前 frontier

### 已落地

| 能力 | 入口 |
|---|---|
| 最小 Agent / ReAct | `minimal.py`、`agent/core.py` |
| 工具调用 + 感知契约 | `agent/tools.py`、`agent/observation.py` |
| 长期记忆（写侧/读侧） | `agent/memory.py`、`agent/extractor.py` |
| Router + Worker | `agent/multi_agent.py` |
| Pipeline / Fan-out / EC | `pipeline.py`、`multi_agent.py`、`evaluator_critic.py` |
| Group Chat / Contract Net / Debate | `group_chat.py`、`contract_net.py`、`debate.py` |
| MCP | `agent/mcp_bridge.py`、`mcp_servers/` |
| 观测 / 评测 | `agent/tracing.py`、`eval_runner.py`、`agent/judge.py` |

### 当前 frontier

- **上下文**：压缩、token 预算、长历史；
- **流式**：流式输出与中断；
- **工具生命周期 + 状态**：后台任务、恢复、审批/沙箱；
- **评测 rigor**：样本量、判分器校准、回归门；
- **长任务/安全**：RunState、checkpoint、resume、权限门禁。

> 书稿里仍标 ⬜ 的是 **第 4、26、32 讲**；
> 第 0、2、12、22 讲还需要按书的语气继续改写。

---

## 七、评测与诚实边界

- **golden set + LLM-as-judge**：14 条题，4 个计权维度 + 合规红线 + 必达项否决；
- **n 小**：结论只对本项目/本模型负责，不当 benchmark；
- **EC 数值题负结果**：同模型 EC 在客观数值题上 **0/6**，会把 9 判成 11、把 771429 当成对；
  边界是 **EC 需要外部独立信号**（不同模型/计算器/测试）；
- **rerank 被否决**：Top-1 反降、延迟 +296ms；不是“组件越多越好”；
- **Blackboard 只调查未实现**，**Planner-Executor 实测否决**；
- 详细数字见各章实测账，不在这里复制。

> 原则：**先证明“病”存在，再决定要不要治；不为未复现的问题增加复杂度。**

---

## 八、安全红线

1. `.env` 已 gitignore，密钥绝不入库；
2. 计算器用 `eval` 仅限个人演示，生产严禁；
3. 高风险操作（删/发/改/钱/重启/批量）必须人机审批；
4. 当前项目**没有完整沙箱/权限系统**，这是明确的下一步，不是已解决项。

---

## 九、文档地图

| 目录 | 内容 |
|---|---|
| [`docs/书/`](docs/书/) | 单文件初稿，适合从头读 |
| [`docs/README.md`](docs/README.md) | 全书目录 + 阅读路径 |
| [`docs/00-索引/`](docs/00-索引/) | 序章、全书目录、学习总结、问题清单、教学大纲、成文规矩 |
| [`docs/01-基础章/`](docs/01-基础章/) | 模型、最小 Agent、感知、上下文 |
| [`docs/02-编排章/`](docs/02-编排章/) | 四种基本编排 + 五种高级结构 + 能力×编排 |
| [`docs/03-实战章/`](docs/03-实战章/) | 记忆、约束与收尾、本地推理 |
| [`docs/04-协议章/`](docs/04-协议章/) | MCP 基础与边界 |
| [`docs/05-收尾章/`](docs/05-收尾章/) | 架构 |
| [`docs/06-可视化/`](docs/06-可视化/) | 交互可视化设计；P1 原型在 [`visualizer/`](visualizer/) |
| [`docs/07-DSH研究/`](docs/07-DSH研究/) | DSH 技术设计与可吸收路线 |
| [`docs/08-日志/`](docs/08-日志/) | 按日期的复盘、审视、重构 |
| [`docs/99-番外/`](docs/99-番外/) | 模型能力与 Agent 编排 |

---

## 十、一句话

> **这个项目不是“再写一个 Agent 框架”，而是把 Agent 的每条回路拆开给你看：
> 它为什么存在、怎么工作、付什么代价、什么时候不该加。**

从 0 到 1 · 2026-09-06 起步；2026-10-20 整理为《Agent 入门》初稿。
