# AI Agent 从 0 到 1 开发全记录

> 用 **DeepSeek + Python**，从零手写一个 **Agent**，最终落地成一个**可视化 Multi-Agent 对话工具（金銮殿）**。
> 本文档完整记录了**开发历程 + 技术理解 + 代码架构 + 使用方法**。

---

## 一、项目简介

这是一个**单 Agent 到 Multi-Agent、再到可视化界面**的完整进阶项目，用最小依赖（`openai` + `flask`）纯手写实现，不依赖 LangGraph/CrewAI 等现成框架——目的是**理解 Agent 的本质**，而非只会调用框架。

最终成果是一个**拟人化的朝堂界面**：皇帝（用户）御座在上，三位拟人化大臣（专家 Agent）分列朝堂，根据问题自动路由给相应大臣奉旨出列、回禀。

---

## 二、环境与依赖

| 项 | 说明 |
|---|---|
| Python | 3.12.10 |
| 依赖 | `openai`（连 DeepSeek）、`python-dotenv`、`flask` |
| 模型 | DeepSeek `deepseek-chat`（V3） |
| API Key | 存于 `.env`（**已加入 .gitignore，绝不入库**） |

> ⚠️ 注意：开发用 DeepSeek **官方开放**的 `deepseek-chat`（V3）。此前环境里的 `deepseek-flash-vision-exp` 是助手环境内部别名，非公开 API 模型。

### 安装
```bash
cd ~/ai-agent
python3 -m venv .venv                       # 建虚拟环境
source .venv/bin/activate                   # Mac/Linux
.venv/bin/pip install -r requirements.txt   # 装依赖
cp .env.example .env                        # 填入 DEEPSEEK_API_KEY
```

---

## 三、开发历程（六步）

### 第 1 步：最小对话 Agent —— 让模型"活"起来
- `01_basic_chat.py`：连接 DeepSeek，完成一次对话。跑通「输入 → 模型 → 回答」最基础链路。

### 第 2 步：ReAct + 工具调用 —— 让 Agent"能办事"
- `02_tool_agent.py`：给 Agent 装**计算器**工具，理解 **ReAct 循环**。
- 这是区分「聊天机器人」与「Agent」的核心一步。

### 第 3 步：命令行交互 + 真实工具
- `03_cli_chat.py` + `agent/core.py` + `agent/tools.py`：模块化，多轮对话记忆，工具升级为 **计算器/时间/天气**。

### 第 4 步：可观测性 —— 让 Agent"看得见"
- `agent/tracing.py`（Tracer 轨迹）+ `04_cli_dashboard.py`：记录每一步思考/调用/结果/回答、token 用量、上下文预算控制。

### 第 5 步：Multi-Agent 开端 —— Router + Worker
- `agent/roles.py` + `agent/multi_agent.py`：多专家分工（math/weather/general），Router 智能路由。

### 第 6 步：可视化朝堂界面 —— 金銮殿
- `app.py`（Flask 后端）+ `templates/index.html`（古风前端）：皇帝御座 + 百官拟人化，可视化调度与轨迹。

---

## 四、项目结构

```
ai-agent/
├── .env / .env.example        # 密钥（.env 已 gitignore）
├── .gitignore
├── requirements.txt
├── README.md                  # 本文件
├── app.py                     # Flask 后端（/api/chat, /api/experts）
├── 01_basic_chat.py           # 第1步：最小对话 Agent
├── 02_tool_agent.py           # 第2步：ReAct + 工具调用
├── 03_cli_chat.py             # 第3步：CLI 交互 + 真实工具
├── 04_cli_dashboard.py        # 第4步：CLI + 追踪/用量
├── agent/
│   ├── __init__.py
│   ├── core.py                # Agent 引擎（模型+工具+ReAct循环+上下文控制）
│   ├── tools.py               # 工具大本营（计算器/时间/天气）
│   ├── tracing.py             # Tracer 追踪器（可观测性）
│   ├── roles.py               # 多专家角色定义
│   └── multi_agent.py         # Multi-Agent 调度器（Router+Worker）
└── templates/
    └── index.html             # 可视化朝堂界面
```

---

## 五、使用方法

### 命令行（单 Agent）
```bash
python3 01_basic_chat.py       # 最小对话
python3 03_cli_chat.py         # 交互 + 真实工具
python3 04_cli_dashboard.py    # 交互 + 追踪/用量（/trace /usage）
```

### 命令行（Multi-Agent）
```bash
python3 -m agent.multi_agent   # Router+Worker，试试"帮我算 123*456"、"上海天气"
```

### 可视化界面
```bash
python3 app.py                 # 启动 Flask
# 浏览器访问 http://127.0.0.1:5000
```

---

## 六、核心概念（地基，务必掌握）

### 1. Agent 的本质
> **Agent 的智能 100% 来自 LLM，它自己不产智能。**
> Agent 干的事是：用一个**循环（ReAct）**，把「一段持续生效的 **prompt**（角色）+ 一个可装载的**记忆**（上下文）+ 一批**工具**（执行手臂）」与 LLM 的决策能力装配起来，让它从"能回答"变成"能办事"。

**关键分工**：
| 角色 | 干什么 |
|---|---|
| LLM（大脑） | 读懂 → 决策（选哪个工具）→ 翻译（写参数） |
| 工具（手臂） | **真正执行**（计算、查天气等，代码实现） |
| function call（神经） | 连接 LLM 决策与工具执行 |
| prompt（剧本设定） | 全程驻留上下文的角色约束 |
| 记忆（上下文） | 短期=history 整段喂入，长期=外部库检索 |

### 2. ReAct 循环
> 思考（Reason）→ 决定行动（Act）→ 观察结果（Observe）→ 再思考，循环到完成。
> 有 `max_steps` 兜底，防止死循环。

### 3. 记忆机制
- **短期记忆**：`self.history` 列表，每轮把**整个历史**再喂给模型。LLM 自身无记忆。
- **长期记忆**：外部存储 / 向量库，通过检索（RAG）把相关片段调回上下文。
- **上下文预算**：`trim_history()` 在历史过长时抹旧保新，防 token 爆炸。

### 4. 可观测性
> Tracer 记录每一步「思考/工具调用/工具结果/回答」+ 耗时 + token。多 Agent 调试与可视化的基础。

### 5. Multi-Agent 架构
> **Router（调度者，只决策）+ Worker（专家，各自人格+工具）**。Router 输出 `{"expert":"..."}` 决定交给谁，委派给对应专家处理，汇总回传。

### 6. Function Calling vs MCP（易混淆）
| | Function Calling | MCP |
|---|---|---|
| 是什么 | OpenAI 定义的**请求格式标准** | Anthropic 定义的**工具生态协议** |
| 管什么 | 单个模型 ↔ 单个工具（一对一） | 工具打包/发现/跨系统复用（一对多） |
| 关系 | 模型调工具用 | 让工具能被任何生态复用 |
| 本项目 | ✅ 用于调工具 | ❌ 未用（后续阶段） |

> 本项目第 2 步用的是 **OpenAI Function Calling**（DeepSeek 兼容 OpenAI 格式），**没用 MCP**。MCP 是让工具成为"标准 USB 插座"的另一套东西，与 Function Calling 不是竞品而是搭档。

---

## 七、金銮殿 · 可视化界面设计

**设计理念**：皇帝（用户）御座在上，大臣（专家 Agent）分列朝堂，拟人化呈现。

| 大臣 | 对应专家 | 形象 |
|---|---|---|
| 工部 · 稽算司 | math | 🧮 |
| 钦天监 · 观象台 | weather | ☁️ |
| 文渊阁 · 大学士 | general | 📜 |

**交互流程**：帝发圣谕 → 百官听旨 → Router 判断 → 奉旨出列（高亮前移）→ 回禀（弹出气泡）→ 可展开「廷议过程」（轨迹）。

**视觉**：古风配色（金/红/宣纸/朱砂）、Noto Serif SC 衬线字体、御座与大臣卡片、响应式适配移动端。

---

## 八、安全红线

1. `.env` 已 `gitignore`，密钥绝不入库。
2. 本项目的计算器工具用 `eval` 演示（个人项目可用，**生产严禁**）。生产需安全沙箱/白名单。
3. 涉及「删、发、改、钱、重启、批量」的高风险操作，必须人机审批，不可由 Agent 自主执行。

---

## 九、已掌握 vs 待探索

**✅ 已掌握**
- Agent = 模型 + 工具 + ReAct 循环
- 记忆机制（短期 history / 长期外部库）
- 可观测性、Multi-Agent 路由调度
- 可视化 Multi-Agent 落地

**⏳ 待探索（进阶方向）**
- 长期记忆（向量库 RAG）
- 真实搜索 / 读网页 / 接数据库等真实工具
- MCP 工具生态
- 更复杂编排（Pipeline / 层级 / Debate）
- 部署上线 + 成本/性能评测

---

*从 0 到 1 · 2026-09-06 全记录。*
