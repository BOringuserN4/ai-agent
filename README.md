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
| 模型 | DeepSeek `deepseek-flash`（V3） |
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
- `/json <schema> <问题>` → 结构化 JSON 输出（math/weather/summary，/json list 查看）
- `/pipe <场景> <问题>` → Pipeline 模式（math_to_summary/research_to_report，/pipe list 查看）
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
├── eval_runner.py        # 评测跑批（golden set + LLM-as-judge，支持 --compare 回归对比）
├── eval_memory_recall.py # 召回质量迷你评测（该召回/不该召回 + 阈值扫描）
├── eval_evaluator_critic.py # Evaluator-Critic 正反例对照实验（轮次×分数 + token 账）
├── LICENSE               # MIT
├── README.md
├── docs/
│   ├── ai-agent-curriculum.md   # 进阶教学大纲（章节版 + 选型/度量/自检）
│   ├── learning-summary.md      # 学习总结（主线图 + 五模块代价 + 被证伪的判断）
│   ├── orchestration-patterns.md # 编排四模式讲义（Router/Pipeline/Fan-out/Evaluator-Critic）
│   ├── agent-mainline.html      # Agent 主线图（单文件，浏览器直接打开）
│   ├── agent-understanding-timeline.html  # 对 Agent 的理解演进时间线（对照纠偏）
│   └── diagrams/
│       ├── agent-mainline.svg
│       └── agent-understanding-timeline.png
├── langfuse/             # Langfuse 自部署（docker-compose，.env 已 gitignore）
└── agent/
    ├── __init__.py
    ├── core.py           # Agent 引擎（模型+工具+ReAct循环+上下文控制+记忆抽取+Langfuse 埋点）
    ├── tools.py          # 工具大本营（计算器/天气/时间）
    ├── tracing.py        # Tracer 追踪器（终端轨迹打印）
    ├── roles.py          # 多专家角色定义（solo 全能 / math / weather / general）
    ├── multi_agent.py    # Multi-Agent 调度器（Router+Worker，判据驱动拆与不拆）
    ├── memory.py         # 长期记忆 RAG（ChromaDB HNSW + DashScope embedding + 阈值闸门）
    ├── extractor.py      # 记忆重要性过滤器（LLM 决策版）
    ├── golden_set.py     # 评测题集（14 条，含边界/跨域/能力边界）
    ├── judge.py          # LLM-as-judge（4 计权维度 + 合规红线 + 必达项否决）
    ├── json_mode.py      # 结构化 JSON 输出（schema-as-prompt）
    ├── pipeline.py       # Pipeline 模式（Agent 串联：上一步输出=下一步输入）
    └── evaluator_critic.py # Evaluator-Critic 模式（生成→批判→不达标重做，代码封顶轮次）
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
> Tracer 记录每一步「思考/工具调用/工具结果/回答」+ 耗时 + token，打印到终端。
>
> **Langfuse v4 埋点**（2026/09/14 补全）：
> - **Trace = 一次完整任务；Span = 任务里的一步**，嵌成父子树，价值在**归因**（哪一步慢/贵/错）。
> - 循环内每次 LLM 调用 → `generation` 子 span（token 归因到步）；每次工具调用 → `tool` 子 span。
> - **失败记 `level=ERROR`**，不静默；根 span 异常先记录再抛出。
> - 验证：查 ClickHouse `events_core` 看 `parent_span_id` 是否有值。
> - 注意：v4 数据先入 `events_core` 表，再异步聚合到 traces 视图表。

### 5. 评测体系（2026/09/10 起）
> **监控答「发生了什么」，评测答「对不对」——两件事。**
> - `golden_set.py`：14 条题（math 3 / weather 2 / general 3 / edge 6）。
> - `judge.py`：LLM-as-judge，4 计权维度 + 合规红线 + **必达项否决**。
> - `eval_runner.py`：跑批/汇总/JSON 落盘，`--compare` 做回归对比。
> - 关键原则：长期记忆必须关（否则题目间污染）；能测量的别让 LLM 判；恒为满分的维度只当一票否决。

### 6. 召回阈值（2026/09/14）
> **top_k 管排序，阈值管资格**，两道闸门分工不同。
> `memory.py` 的 `search()` 加 `min_score=0.6`：实测该召回组 `0.68~0.86`、不该召回组 `0.44~0.52`，
> 空档中点即阈值。**分数跨模型不可比**，换 embedding 需重跑 `eval_memory_recall.py` 阈值扫描。
> Tracer 记录每一步「思考/工具调用/工具结果/回答」+ 耗时 + token——多 Agent 调试与可视化的基础。

### 7. Multi-Agent 架构（2026/09/15 重构）
> **Router**（调度者，只决策）输出 `{"reason": ..., "tasks": [...]}`，判定拆或不拆，**Worker** 执行后汇总回传。
>
> **核心原则：多 Agent 不是能力升级，是成本结构。** 每多一个 agent 就多付一份交接损耗+压缩上下文+token。
> 只有当「单 Agent 做不到」时才值得拆，**跨域 ≠ 该拆**。
> Router 默认走 `solo`（工具全开的全能单 Agent）；四条判据（上下文隔离/真并行/不同视角/超容量）满足其一才拆。
> 实测：同一道跨域题，拆 2 专家 3624 token → 判「不拆」2242 token，质量不变。

### 8. 智能记忆抽取（LLM 决策）
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

- ~~长期记忆（向量库 RAG）~~ ✅ 已完成（ChromaDB HNSW + DashScope 远程 embedding）
- ~~智能记忆抽取（LLM 过滤）~~ ✅ 已完成（extractor.py）
- ~~结构化 JSON 输出~~ ✅ 已完成（json_mode.py：/json <schema> <问题> 触发）
- ~~Pipeline 模式~~ ✅ 已完成（pipeline.py：/pipe math_to_summary/research_to_report）
- ~~Langfuse 可观测性~~ ✅ 已完成（core.py 内埋点，含失败可见）
- ~~评测框架（golden set + LLM-as-judge）~~ ✅ 已完成（eval_runner.py）
- ~~召回质量评测 + 阈值闸门~~ ✅ 已完成（eval_memory_recall.py + memory.py）
- ~~多 Agent 拆与不拆的判据~~ ✅ 已完成（multi_agent.py 重构）
- ~~Evaluator-Critic 编排~~ ✅ 已完成（evaluator_critic.py，实测见第八节）
- Router 成本优化（当前每条都问 LLM，约 850 token/次 → 加规则预筛）
- 真并行 Fan-out（当前串行 `for` 循环）
- MCP 工具生态
- 可视化界面

---

## 八、Evaluator-Critic 实测（2026/09/16）

`agent/evaluator_critic.py` 实现了本项目第 4 种编排模式：**生成 → 批判 → 不达标重做**。
它与前三种（Router / Pipeline / Fan-out）的结构差别在于——这是第一个「**监督关系**」：
一个角色管另一个角色的质量，而不是平级分工。

### 为什么批判者必须独立（判据③）
让生成者自己批自己会撞上**自我确认偏差**：它刚做完推理，再让它挑错会倾向于辩护。
所以批判者要是**另一个立场**。注意关键是「立场独立」，不是「必须两个 Agent 实体」——
同一 Agent 换批判人格 + 清掉生成时上下文也算。

### 分数怎么算（代码定规则，裁判只提供事实）
- 硬性要求不合规 → **一票否决，封顶 59**（对应 judge.py 的 must_have 思路）；
- 合规后，60-100 分由裁判给的三个「手艺分」（场景绑定 / 差异化 / 语感节奏，各 0-10）**加权折算**；
- **阈值和加权都是人的决策**，裁判只负责提供事实，换题不改口径。

### 实测账（`eval_evaluator_critic.py`）
| 场景 | 轮次 | 分数轨迹 | token | 结论 |
|---|---|---|---|---|
| 正例 · 硬约束文案（及格线 85） | 3 | 84 → 84 → 85 | 14865 | 达标，重做确实把分数推上去了 |
| 反例 · 缺信息（命中否决线④） | 3 | 59 → 59 → 59 | 9437 | 走平，**批了也改不动**，钱白花 |
| 追加实拍 · 及格线拧到 90 | 3 | 84 → 87 → 59 | 24211 | **回退**：为凑手艺分把硬约束写崩 |

三条结论：
1. **否决线④是真的**：缺信息时，批判再准也无法改进，只有 token 在涨；
2. **及格线是根旋钮**：85 能在两三轮内收敛，90 会诱发「牺牲硬约束换手艺分」的退步；
3. **循环必须由代码封顶**：否则「不达标就重做」会一直烧钱——本实现上限 3 轮，封顶后输出历史最好的一版。

---

## 九、进阶教材

主体代码完成后，下一步推荐读 [`docs/ai-agent-curriculum.md`](docs/ai-agent-curriculum.md) ——这是一份**章节版进阶路线**：

- 10 种多 Agent 编排模式（Router / Pipeline / Evaluator-Critic / Fan-out …）
- 资源/成本选型对比（DeepSeek / DashScope / LangGraph / Qdrant …）
- 4 象限度量体系（效果/效率/成本/可靠性）
- 6 条 2026 趋势研判
- 学习路径自检清单（避坑 + 敏感操作分级）

适合完成主体学习后进阶时配合实操使用。

---

*从 0 到 1 · 2026-09-06 起步，2026-09-07 收敛为 Multi-Agent 工程形态，2026/09/15 完成可观测/评测/召回阈值/多 Agent 判据，学习总结见 `docs/learning-summary.md`。*
