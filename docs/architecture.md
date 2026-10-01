# 架构图 · ai-agent 模块结构与运行时数据流

> 阶段一收口的最后一块：**能把每个模块为什么这样设计讲清楚**。
> 本文含两张图（手绘风）+ 分层依据 + 依赖规则 + 工具选型记录。
> 完成日期：2026/10/01。

**图**（手绘风，roughjs 生成；源文件在同名 `.svg`）：

| 图 | 文件 | 内容 |
|---|---|---|
| 分层架构图 | `docs/diagrams/architecture-sketch.png` | 四层结构 + 10 个纯叶子 |
| 运行时数据流 | `docs/diagrams/architecture-flow.png` | 一次对话的全过程 + 两处记忆时点 |

备选（可重渲版）：`docs/architecture.d2` → `architecture-d2.png`（D2 自动布局）。

---

## 1. 是什么

**一张按「依赖方向」分层的模块结构图，加一张运行时数据流图。**

不是概念图（那有 `agent-mainline.html`），而是**照着实测依赖关系画的工程图**：
17 个模块谁依赖谁、分几层、数据怎么流。

---

## 2. 结构定位：四层

**分层依据**：AST 实测的依赖深度（拓扑序），不是拍脑袋分的。

```
① 应用层    main.py · multi_agent · pipeline · evaluator_critic
                 ↓ 依赖
② 引擎层    core（ReAct 主干）· roles · json_mode
                 ↓ 依赖
③ 能力层    memory（有状态）
                 ↓ 依赖
④ 组件层    embedding_backends · extractor · tools · tracing · router_prefilter
            rerank · tool_selector · mcp_bridge · judge · golden_set   （10 个纯叶子）
```

**实测数据**：

| 模块 | 行数 | 依赖 |
|---|---|---|
| `core` | 385 | extractor, memory, tools, tracing |
| `evaluator_critic` | 320 | core, json_mode |
| `golden_set` | 295 | **（纯叶子）** |
| `embedding_backends` | 276 | **（纯叶子）** |
| `multi_agent` | 265 | core, memory, roles, router_prefilter |
| `memory` | 253 | embedding_backends, rerank |
| `json_mode` | 238 | core, tracing |
| `extractor` / `judge` / `mcp_bridge` | 216/215/215 | **（纯叶子）** |
| `pipeline` | 177 | json_mode |
| `rerank` / `tools` / `tool_selector` | 163/160/150 | **（纯叶子）** |
| `router_prefilter` | 132 | **（纯叶子）** |
| `roles` | 70 | core |
| `tracing` | 57 | **（纯叶子）** |

**核心度**（被多少模块依赖）：`core(4)` > `tracing(2) = memory(2) = json_mode(2)` > 其余(1)

---

## 3. 为什么这么设计

### 3.1 依赖方向：依赖倒置

**规则：上层可以依赖下层，下层绝不依赖上层。**

如果 `tools.py` 去 import `core.py`，会形成循环依赖；更本质的问题是
**工具不该知道「谁在用它」**。

> **越底层越「无知」，越上层越「知道全局」。**

### 3.2 那 10 个纯叶子的共同点（本图的重点）

看它们各自是什么：

| 模块 | 职责 |
|---|---|
| `embedding_backends` | 向量化（云端/本地可换） |
| `rerank` | 精排（可开可关） |
| `tool_selector` | 工具裁剪 |
| `router_prefilter` | 路由预筛 |
| `mcp_bridge` | MCP 桥接 |
| `extractor` | 记忆过滤 |
| `judge` | 评测评委 |
| `golden_set` | 评测题集 |
| `tools` | 工具函数 |
| `tracing` | 轨迹记录 |

**共同点有三层，一层比一层深**：

**第一层 · 都是可替换的零件**
每个只做一件事，换掉它不影响别处。

**第二层 · 都不知道 Agent 的存在**
只有「进 → 出」的纯契约，没有上下文感知。
→ **所以能独立测试** —— 项目里 10 个 `eval_*.py` 能存在正是因为这个：
`eval_rerank.py` 可以**单独**测精排，不必启动整个 Agent。

**第三层 · 把「决策」从「执行」里拆了出来**

```
router_prefilter（规则）  +  Router（LLM）    = 路由决策
tool_selector（规则）     +  工具列表         = 工具决策
embedding_backends（执行）+  阈值判断         = 检索决策
```

→ 正因为决策被拆开，才能做 `docs/rerank-layer.md` 里那个 A/B 实验：
**把 rerank 插进去、拔出来，对比 Top-1 变好还是变坏**。
如果精排写死在 `memory.py` 里，根本测不了。

> **一句话**：**纯叶子 = 可替换的策略；它们不依赖引擎，所以引擎才能换策略。**

### 3.3 运行时数据流：记忆被用到两次

```
用户输入
   ↓
multi_agent._plan()  ← 先规则预筛（零 token），不确定才问 LLM Router
   ↓
core.Agent.run()     ★ 记忆时点 ①：提问前
   │   memory.search() → embedding_backends → ChromaDB top-K →（rerank）
   │   → 召回结果注入 system prompt
   ↓
ReAct 循环（LLM ⇄ tools 执行 ⇄ 结果回流；每步 tracing + Langfuse）
   ↓
返回回答
   ↓
★ 记忆时点 ②：回答后（**后台线程**）
   extractor.extract() → memory.add()
```

| 记忆时点 | 干什么 | 为什么在这 |
|---|---|---|
| **① 提问前** | `search()` 召回 → 注入上下文 | 模型必须**在生成前**看到记忆 |
| **② 回答后** | `extract()` 判断 → `add()` 写入 | 用**完整对话**判断值不值得记 |

> ②跑在后台线程（`core.py` 的 `threading.Thread`）——
> **「并发」在本项目里早就存在**，不是后来才加的。

---

## 4. 代价（值钱那行）

| 代价项 | 说明 |
|---|---|
| **纯叶子数量多** | 10 个模块要各自维护，接口一多变更多 |
| **分层是"约定"，无强制** | Python 不阻止你反向 import，靠人守 |
| **图会过期** | 加模块必须重跑生成器，否则图与代码不一致 |
| **手绘版布局是硬编码坐标** | 改结构要改生成器代码（D2 版没这问题） |
| **看不出"运行时量级"** | 图只画结构，不表达延迟/成本（那些在各自讲义里） |

---

## 5. 代码在哪

| 文件 | 说明 |
|---|---|
| `docs/gen-arch-sketches.js` | 手绘版生成器（roughjs，含两张图） |
| `docs/architecture.d2` | D2 版源文件（备选，自动布局） |
| `docs/diagrams/architecture-sketch.svg/.png` | 分层架构图 |
| `docs/diagrams/architecture-flow.svg/.png` | 运行时数据流 |
| `docs/diagrams/architecture-d2.svg/.png` | D2 备选版 |

---

## 6. 怎么跑

```bash
# 手绘版（推荐）——需要 roughjs
cd /tmp/sketch && npm i roughjs && cp ~/ai-agent/docs/gen-arch-sketches.js .
node gen-arch-sketches.js ~/ai-agent/docs/diagrams

# D2 版（备选；自动布局）
d2 docs/architecture.d2 docs/diagrams/architecture-d2.svg
```

---

## 7. 实测账：工具选型与渲染踩坑

### 7.1 试了三个工具

| 工具 | 结果 | 特点 |
|---|---|---|
| **roughjs**（选定） | ✅ | **Excalidraw 内部同款渲染库**，手绘自然；但布局要手算坐标 |
| **D2**（d2lang） | ✅ | 声明式 DSL + **自动布局**，改几行重渲；风格工整 |
| Mermaid | ⏹ 放弃 | 正是"md 式"的观感；且 `mermaid-cli` 要下 Chromium（代理下太慢） |

**选 roughjs 的理由**：用户要"自然"的观感 → 手绘风；且布局可控，不跟自动布局打架。

### 7.2 D2 的两个布局陷阱（实测）

1. **各层必须包在一层 root 容器里 + `direction: down`**，
   否则四个层容器会被排成一行（曾出现 **5160px 宽**的横排图）
2. **绝不能用 `grid-columns`** —— 它会让容器**横排**
   （二分实验：grid 变体 3.29:1，`direction: right` 变体 0.69:1）

### 7.3 渲染踩坑：qlmanage 会裁切

**`qlmanage -t` 输出正方形、顶对齐** —— 宽图会被**从右边裁掉**。

第一版 D2 图据此误判成"文字溢出"，实际是**裁切造成的假象**。

→ 改用 **resvg**（`@resvg/resvg-js`）：按宽度精确渲染，不裁切。

> 这条已可回写到 `diagram-render-qa` 技能：**宽图别用 qlmanage，用 resvg**。

### 7.4 修正一处我自己的错误

我在讲解第 1 题时，把 `extractor` / `tools` / `tracing` 归到了「**能力层**」；
但第 2 题的 AST 数据同时显示它们是**纯叶子**——**两处自相矛盾**。

本图以**事实为准**：它们归入**组件层**。
（根因：我先凭印象分层的句子，写在了跑 AST 之前。）

---

## 8. 结论

1. **四层结构由依赖方向决定**，不是人为划分：应用 → 引擎 → 能力 → 组件
2. **10 个纯叶子是全项目的"可替换策略层"**：不认识 Agent，所以能独立测试、
   能 A/B 对比、能整体换掉
3. **记忆被用两次**（提问前召回 / 回答后沉淀），且后者异步
4. **架构图应该是"可重生成的"**，不是一次性手绘——所以留了生成器而非只留图

---

## 9. 踩过的坑

| 坑 | 说明 |
|---|---|
| **先凭印象分层，再跑 AST** | 导致 `extractor/tools/tracing` 被错放「能力层」，与自己的另一段答案矛盾。**先测再画。** |
| **qlmanage 裁切宽图** | 误判成"文字溢出"。**宽图用 resvg。** |
| **D2 的 grid-columns 破坏竖排** | 二分实验才定位到（vA 0.69:1 vs vB 3.29:1）。 |
| **`anchor:end` 让文字压进别的框** | 数据流图里"召回结果注入…"一行右对齐，直接压进了 `memory.search` 框。**QA 抓到，已改为左对齐放框下。** |
| **roughjs 的 bundled 版不含 SVG 生成器** | `roughjs/bin/svg` 依赖 DOM。改用 `rough.generator()` + 自己序列化 ops。 |
