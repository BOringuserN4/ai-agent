# 项目文档地图（`docs/`）

> **这是什么**：本项目（`~/ai-agent`）从 0 到 1 学习 AI Agent 工程的全部讲义。
> 27 份文档，按**章**组织；每份都可独立阅读，也可按下面的路径串读。
> **怎么用**：先看「三条阅读路径」选一条 → 再按下表点到具体讲义。
> 最后更新：2026/10/07。

---

## 一、三条阅读路径（按目的选）

### 🅰 第一次读（建议按序）
> 目的：建立整体印象，知道「Agent 是什么、由什么组成」。

1. [`01-基础章/capability-ladder.md`](01-基础章/capability-ladder.md) — 从 88 行到 5000 行，一条纵向代码阶梯
2. [`02-编排章/orchestration-patterns.md`](02-编排章/orchestration-patterns.md) — 四种编排模式（最小到进阶）
3. [`03-实战章/constraints-and-termination.md`](03-实战章/constraints-and-termination.md) — 约束与收尾（为什么不能「撞墙才停」）
4. [`05-收尾章/architecture.md`](05-收尾章/architecture.md) — 分层架构 + 运行时数据流
5. [`00-索引/learning-summary.md`](00-索引/learning-summary.md) — 学习总结（主线 + 核心结论）

### 🅱 按主题速查（已有具体问题）
> 目的：手上有个具体问题，只想看那一块。

| 想知道 | 看这里 |
|---|---|
| 怎么省钱（token/成本）| [`02-编排章/router-cost.md`](02-编排章/router-cost.md) |
| 慢工具怎么提速 | [`02-编排章/fanout-parallel.md`](02-编排章/fanout-parallel.md) |
| 记忆检索不准 | [`03-实战章/memory-recall-fix.md`](03-实战章/memory-recall-fix.md) |
| 记忆跨轮指代丢失 | [`03-实战章/memory-chunking.md`](03-实战章/memory-chunking.md) |
| 工具怎么跨框架复用 | [`04-协议章/mcp-basics.md`](04-协议章/mcp-basics.md) |
| 多 Agent 怎么协作 | [`02-编排章/decentralized-investigation.md`](02-编排章/decentralized-investigation.md) |

### 🅲 复盘「怎么得出结论的」（学方法论）
> 目的：不是学结论，是学**怎么验证一个结论**。

[`00-索引/learning-summary.md`](00-索引/learning-summary.md) §「被证伪的判断」+
[`00-索引/issue-log.md`](00-索引/issue-log.md)（40 条踩坑）+ 各「调查」类讲义。

---

## 二、全部文档一览（按章）

### 📘 00-索引/（总纲与清单）

| 文档 | 一句话 |
|---|---|
| [`ai-agent-curriculum.md`](00-索引/ai-agent-curriculum.md) | **教学大纲**：12 节，从 Agent 本质到趋势研判 |
| [`learning-summary.md`](00-索引/learning-summary.md) | **学习总结**：主线 + 五模块 + 被证伪的判断 + 核心结论 |
| [`issue-log.md`](00-索引/issue-log.md) | **已发现问题清单**：40 条踩坑，按主题归类 |
| [`issue-log-review-2026-10-07.md`](00-索引/issue-log-review-2026-10-07.md) | 问题清单的**系统性复核**（抓到 6 处「现状」腐坏）|
| [`authoring-rules.md`](00-索引/authoring-rules.md) | **成文规矩**：讲义怎么写（固定六段 + 写作原则）|

### 📗 01-基础章/（Agent 的本质）

| 文档 | 一句话 |
|---|---|
| [`capability-ladder.md`](01-基础章/capability-ladder.md) | 能力阶梯：从 88 行到 5000 行，每级独立可运行 |
| [`perception-structured-investigation.md`](01-基础章/perception-structured-investigation.md) | 感知-行动回路结构化（`{ok,data,error}` 契约）|

### 📙 02-编排章/（多 Agent 怎么组织）

| 文档 | 一句话 |
|---|---|
| [`orchestration-patterns.md`](02-编排章/orchestration-patterns.md) | 编排四模式讲义（Router / Pipeline / EC / Fan-out）|
| [`router-cost.md`](02-编排章/router-cost.md) | Router 成本优化（规则预筛，省 25%）|
| [`fanout-parallel.md`](02-编排章/fanout-parallel.md) | 真并行 Fan-out（判据②：独立 + 资源可吸收）|
| [`planning-investigation.md`](02-编排章/planning-investigation.md) | 显式规划调查 → **实测否决** |
| [`hierarchical-investigation.md`](02-编排章/hierarchical-investigation.md) | 层级编排 / 工人池 → **条件性必要** |
| [`decentralized-investigation.md`](02-编排章/decentralized-investigation.md) | 去中心化协商（Group Chat）→ 信息分散时不可替代 |
| [`contract-net-investigation.md`](02-编排章/contract-net-investigation.md) | Contract Net（发标-投标-中标）→ 中央无法评估时必要 |

### 📕 03-实战章/（记忆 · 成本 · 稳定性）

| 文档 | 一句话 |
|---|---|
| [`constraints-and-termination.md`](03-实战章/constraints-and-termination.md) | 约束与收尾（截断 + 预算预警 + 收尾步）|
| [`memory-extraction.md`](03-实战章/memory-extraction.md) | 记忆抽取：评测与本地化评估 |
| [`memory-recall-fix.md`](03-实战章/memory-recall-fix.md) | 记忆召回修复（增量式文本增富）|
| [`memory-chunking.md`](03-实战章/memory-chunking.md) | 记忆切分粒度（跨轮指代消解）|
| [`memory-cases.md`](03-实战章/memory-cases.md) | 记忆用例评测（端到端：答案有没有变）|
| [`embedding-upgrade.md`](03-实战章/embedding-upgrade.md) | 换更强 embedding（v3→v4）+ 阈值重推导 |
| [`rerank-layer.md`](03-实战章/rerank-layer.md) | 精排层（rerank）→ **实测否决** |
| [`local-inference.md`](03-实战章/local-inference.md) | 本地推理（embedding 挪到局域网 Ollama）|

### 📔 04-协议章/（工具与 Agent 的接口）

| 文档 | 一句话 |
|---|---|
| [`mcp-basics.md`](04-协议章/mcp-basics.md) | MCP 基础：把工具变成通用插座（N×M → N+M）|
| [`mcp-boundary.md`](04-协议章/mcp-boundary.md) | 边界辨析：记忆该不该 MCP 化？|

### 📓 05-收尾章/（整体视图）

| 文档 | 一句话 |
|---|---|
| [`architecture.md`](05-收尾章/architecture.md) | 架构图：分层结构 + 运行时数据流 |

### 📖 99-番外/（延伸阅读）

| 文档 | 一句话 |
|---|---|
| [`model-capability-vs-agents.md`](99-番外/model-capability-vs-agents.md) | 模型能力提升对 Agent 的影响（文献综述）|

### 🗄 历史归档/

| 文档 | 一句话 |
|---|---|
| [`session-2026-09-19.md`](历史归档/session-2026-09-19.md) | 往期会话记录（**历史语境**，勿当现状读）|

> 另有两个非讲义目录：`diagrams/`（图）、`experiments/`（实验脚本）、`tools/`（图生成器）。

---

## 三、写作与维护约定

- **讲义结构**：每份按固定六段（是什么 / 结构定位 / 为什么这么设计 / **代价** / 代码在哪 / 怎么跑 / 实测账）。
  详见 [`00-索引/authoring-rules.md`](00-索引/authoring-rules.md)。
- **数据要实测**：「明显更快」不算，`2650 token / 2.7s` 才算。
- **⚠️ 历史归档勿当现状**：`历史归档/` 与实验里的对照臂名（「甲·现状」）是**当时**的语境。
- **腐坏防治**：`现状 / 尚未 / ⬜` 这类措辞最易过时（见 [`issue-log`](00-索引/issue-log.md) #38/#39）；
  每周有 `doc-freshness-review` 巡检自动检查。

---

## 四、一张图看懂文档间关系

```
                     ┌──────────────┐
                     │ 教学大纲     │  ← 00-索引/ai-agent-curriculum.md（总纲）
                     └──────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   01-基础章            02-编排章            03-实战章
   （本质）             （组织）             （记忆/成本/稳定）
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                     05-收尾章 架构图（整体）
                            ▼
                     00-索引 学习总结（结论）
                            ▼
                     00-索引 issue-log（踩坑）
```

> 各「调查」类讲义（`*-investigation.md`）统一遵循「先证明病存在 → 实测 → 给边界」的写法：
> 结论不是学到的，是**测出来的**。
