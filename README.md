# AI Agent 开发学习项目

从 0 开始，用 DeepSeek + Python 手写一个 Agent，逐步走向可视化 Multi-Agent 对话工具。

## 环境
- Python 3.12
- `openai` 库（连接 DeepSeek，DeepSeek 兼容 OpenAI 格式）
- DeepSeek API key（放在 `.env`，格式见 `.env.example`）

## 当前进度（单 Agent 阶段）

| 文件 | 作用 | 状态 |
|---|---|---|
| `01_basic_chat.py` | 最小对话 Agent，连接模型回答问题 | ✅ |
| `02_tool_agent.py` | ReAct + 工具调用（计算器），理解 Agent 核心 | ✅ |
| `03_cli_chat.py` | 命令行交互入口，多轮对话 + 真实工具 | ✅ |
| `agent/core.py` | Agent 引擎（模型 + 工具 + ReAct 循环） | ✅ |
| `agent/tools.py` | 工具大本营（计算器 / 时间 / 天气） | ✅ |

## 怎么跑

```bash
cd ~/ai-agent
cp .env.example .env       # 第一次：填好 DEEPSEEK_API_KEY
source .venv/bin/activate  # 激活虚拟环境
python3 03_cli_chat.py     # 启动命令行 Agent
```

## Agent 支持的能力
- 自由对话（多轮记忆）
- 四则运算
- 当前时间 / 时区
- 查询城市天气（北上广深杭蓉）

## 核心概念（地基）
- **Agent = 模型 + 工具 + ReAct 循环**
- 模型只负责「读懂 → 决策 → 翻译参数」；工具的真实执行体在你代码里
- ReAct = 思考 → 行动 → 观察 → 再思考，循环到完成（有 max_steps 防死循环）
- Function Calling 是操作系统，MCP 是标准插座（后面的阶段）

## 开发路线（往多 Agent）
1. ✅ 单 Agent 打地基（ReAct + 工具）
2. ⬜ 命令行交互 + 真实工具（本步完成）
3. ⬜ 加入日志/追踪，可观测
4. ⬜ 抽象出可复用的 Agent 接口
5. ⬜ 多 Agent 编排（可视化）

## 安全
- `.env` 已加入 `.gitignore`，密钥不会提交
- 生产环境请改用安全的工具调用（不用 `eval` 直接执行算术）
