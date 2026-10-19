# DeepSeek Harness 技术设计与实现：一份可吸收的架构笔记

> 研究对象：本机 DSH Desktop **0.2.1-rc.2**（2026-10-17 构建）。
> 依据：DSH 包内 `README.zh.md`（设计说明）、源码地图、关键实现约定；
> app.asar 内是打包后的 `lib/*.js`，本文**没有逐行反编译**，而是按“设计文档 + 源码地图 + 关键机制”整理。
> 目的：为 `ai-agent` 提炼可吸收的技术点；具体落地见 [可吸收技术点与路线](可吸收技术点与路线.md)。

---

## 0. 一句话理解 DSH

> **DSH 不是“一个更聪明的 Agent”，而是一套“事件溯源 + 能力接口 + 插件组合”的 Agent 运行时。**

三根支柱：

1. **会话是事件日志**：发生的每件事按顺序写进 `Session`；模型历史、统计、UI、持久化都从日志算出来。
2. **能力是可替换接口（seam）**：工具、LLM、沙箱、审批、技能、子 Agent 都是注册表 + 提供方。
3. **组合是插件树**：`dsh-base` 提供核心插件，profile 决定装哪些；`agent-preset` 决定每个 Agent 装哪些子插件。

它和 LangGraph/CrewAI 的区别：DSH 不是“画图 DSL”，而是**运行时**——
会话、工具、权限、技能、子 Agent、后台任务、调度、目标，都是运行时的一部分。

它和你的 `ai-agent` 的区别：你的项目是**白盒教学实现**；DSH 是**生产级外壳**。
本文只吸收“机制”，不复制“体量”。

---

## 1. 总体架构

```
┌────────────────────────────────────────────────────────────┐
│ UI / Transport：Web GUI、ACP、SDK、headless                 │
├────────────────────────────────────────────────────────────┤
│ API / Session Controller：会话列表、投影、控制面             │
├────────────────────────────────────────────────────────────┤
│ Agent Registry + AgentLoop：轮次 / 步骤 / 收件箱 / 工具调度  │
├────────────────────────────────────────────────────────────┤
│ Session Log（事件溯源）+ Projections + Persistence          │
├────────────────────────────────────────────────────────────┤
│ Context Assembly：System Prompt、AGENTS.md、Skills、        │
│                    Token Meter、Compaction、Spill           │
├────────────────────────────────────────────────────────────┤
│ Tool Runtime：fs / bash / web / subagent / workflow / jobs  │
│               + Permission / Approval / Sandbox             │
├────────────────────────────────────────────────────────────┤
│ LLM Runtime：Provider Adapter、Stream、Retry                │
├────────────────────────────────────────────────────────────┤
│ Observability：OTel、Session Telemetry、Stats               │
└────────────────────────────────────────────────────────────┘
```

### 1.1 包的分组（按职责，不按目录）

| 组 | 代表包 | 职责 |
|---|---|---|
| **Agent 核心** | `dsh-agent`、`dsh-agent-loop` | Agent 句柄、轮次/步骤状态机、收件箱、工具调度 |
| **会话** | `dsh-session`、`dsh-session-persistence-jsonl`、`dsh-session-projection` | 事件日志、JSONL 持久化、投影 |
| **上下文** | `dsh-system-prompt`、`dsh-agent-instructions`、`dsh-token-meter`、`dsh-compaction-basic` | 提示词组装、AGENTS.md、计量、压缩 |
| **工具** | `dsh-tools`、`dsh-tool-fs`、`dsh-tool-bash`、`dsh-tool-web` | 工具注册、执行流水线、具体工具 |
| **权限** | `dsh-permission-presets`、`dsh-user-approval`、`dsh-sandbox` | 预设、一次性审批、进程沙箱 |
| **子 Agent** | `dsh-subagent`、`dsh-tool-subagent` | 委派、生命周期、fork/spawn |
| **编排** | `dsh-workflow`、`dsh-tool-workflow`、`dsh-workflow-ptc` | JS 编排脚本、扇出、PTC 执行 |
| **长任务** | `dsh-jobs`、`dsh-schedule`、`dsh-goal` | 后台任务、定时提醒、持久目标 |
| **技能** | `dsh-skill`、`dsh-skill-filesystem`、`dsh-tool-skill` | 技能注册表、本地发现、按需加载 |
| **LLM** | `dsh-llm`、`dsh-llm-deepseek`、`dsh-llm-retry` | Provider 无关流、DeepSeek 适配、重试 |
| **观测** | `dsh-otel`、`dsh-session-telemetry`、`dsh-session-stats` | OTel 通道、遥测、统计 |

> 组合方式：`dsh-base` 是一套基础插件行；profile 是“再加哪些、改哪些”；
> `agent-preset` 是“每个 Agent 挂哪些子插件”。这三层把“产品默认值”和“单 Agent 能力”分开了。

---

## 2. 核心循环：turn / step

### 2.1 轮次与步骤

- **Turn（轮次）**：一次用户输入到 Agent 空闲。
- **Step（步骤）**：一次模型调用 + 它产生的工具调用。
- **Inbox（收件箱）**：用户消息、steering（中途引导）、排队工作；每次变更都写 `agent/inbox/*` 事件。

一个步骤的骨架：

```
claim inbox（领取输入）
  → agent/pre-step（可拦截/改写）
  → agent/request waterfall（模型/参数解析）
  → prepareCall（适配器校验、默认值）
  → assemble system prompt + tools
  → derive messages（从会话日志派生）
  → stream LLM
  → 工具调用（独占 or 并行安全）
  → 结果写回会话日志
  → 下一步 / 结束
```

### 2.2 关键设计

- **模型可见即已记录**：任何进入请求的内容都必须能从会话日志重建。
- **请求是冻结的纯函数**：Loop 构建的请求深度冻结；监听器和适配器只能读，不能改。
- **工具调用有“独占”和“并行安全”两种**：`maxParallelToolCalls` 限制并行安全调用；
  独占调用形成排序屏障。
- **取消是协作式的**：`agent.cancel()` 中止当前活动；已流式交付给用户的文本会保留；
  被取消的流写一条 `interrupted: true` 的 assistant 锚点。
- **重试在步骤边界**：`dsh-llm-retry` 先写“计划重试”的事件，再等；崩溃不会留下不可见的重试。
- **压缩在步骤边界**：token 压力升高 → 压缩旧历史；上下文溢出 → 压缩后重试。

> 教学点：**Agent 的“循环”不是 `while True`，而是一个有明确边界的 turn/step 状态机。**
> 你的 `core.py` 现在是 `for step in range(...)`；DSH 把它拆成了可观测的事件与可恢复的状态。

---

## 3. 会话 = 事件溯源

### 3.1 什么是事件溯源（一句话）

> 不存“当前状态”，存“发生过的每件事”；当前状态 = 从头折叠这些事件。

DSH 的 `Session` 是**仅追加**的类型化事件日志。模型历史、transcript、统计、标题、
持久化、UI 投影，全部从这条流派生。

### 3.2 事件家族（示例）

| 家族 | 例子 | 作用 |
|---|---|---|
| 会话 | `session/created`、`session/flush`、`session/disposed` | 生命周期 |
| 轮次 | `turn/start`、`turn/end` | 一轮的边界 |
| 步骤 | `step/start`、`step/end` | 一步的边界 |
| 消息 | `user/message`、`assistant/message`、`system/message` | 模型可见内容 |
| 尝试 | `assistant/attempt` | 失败/重试/取消，不进模型历史 |
| 工具 | `tool/call`、`tool/result` | 工具执行 |
| 压缩 | `compaction/start`、`compaction/summary`、`compaction/prune` | 上下文压缩 |
| Agent | `agent/inbox/*`、`agent/request*`、`agent/created` | 驱动器状态 |
| 子 Agent | `subagent/descriptor`、`subagent/catalog` | 委派与目录 |
| 目标 | `goal/change` | 持久目标 |

### 3.3 Surface（模型可见面）

- `surface` 是“从事件日志算出的当前模型可见视图”。
- 压缩会**隐藏**被取代的条目，但**不删除**它们；原始事件仍在日志里。
- `replaceGeneration` / `contentGeneration` 跟踪“位置替换”和“插件拥有的消息变更”。
- 回放可以精确恢复“当时模型看到了什么”。

### 3.4 持久化

- 每个会话一个 **JSONL** 日志；默认 Zstandard 压缩帧 + 校验和。
- **单写者**：每个会话一个写句柄，跨进程用文件锁。
- **崩溃恢复**：撕裂尾部可修复；中断的轮次补写 `step/end`。
- **格式代际**：读取器拒绝退役格式；迁移链在构造 `Session` 前转换。
- **fork**：只闭合开放尾部，不修复已闭合步骤的缺失结果。

### 3.5 投影（Projection）

- 投影是“从已提交事件折叠出的当前值”，例如 `sessionStats`、`tokenUsage`、`contextPressure`、`contextBreakdown`、todos、goals。
- 投影有 `asOfSeq`：快照标明“反映到哪个事件”，客户端可把状态与历史切面对齐。
- 为什么重要：**UI 不需要重放原始日志**；它读投影。
  这也是你做“Agent 交互动画”的关键——动画可以订阅投影/事件，而不是自己猜状态。

---

## 4. 上下文工程

### 4.1 系统提示词是“组装”出来的

`dsh-system-prompt` 是注册表 + 组装流水线：

- 全局层 + agent 作用域层；
- 段（segment）按数值/名称排序；
- `system-prompt/assemble` waterfall 可插入/替换；
- 工具 schema 属于组装结果（“模型获知自己能做什么”是一个整体）；
- 无效组合/未解析变量会**组装失败**，不会发格式错误的提示词。

### 4.2 AGENTS.md 是“持久对话内容”

`dsh-agent-instructions`：

- 读用户全局 + 项目级 `AGENTS.md` / `CLAUDE.md`；
- 从项目根到 cwd 的指令链，按“宽泛 → 具体”排序；
- 字节预算：宽泛文件先省略，具体文件最后截断；
- 注入是普通的带来源 `user/message` 事件，**可回放、可压缩、可恢复**；
- 没有 watcher：成功的 `read/write/edit` 或恢复对账时刷新。

### 4.3 Token Meter：给每个决策定价

`dsh-token-meter`：

- 回放持久日志，结果确定，不调用模型；
- 有提供方用量且 envelope 完全匹配 → 用精确值；否则用固定启发式（约 4 字符/token + 结构开销）；
- 提供 `tokenUsage`、`contextPressure`、`contextBreakdown` 三个投影；
- 压缩、占用显示、遥测共享同一套测量。

### 4.4 Compaction：旧历史摘要，不删日志

`dsh-compaction-basic`：

- token 压力上升 → 把最旧的历史摘要，保留近期消息；
- 上下文溢出 → 压缩后重试；
- `/compact` 手动触发；
- 摘要请求复用提供方的热前缀（系统提示词 + 工具 + 被遮蔽消息），只让尾部指令和摘要输出未缓存；
- 工具结果修剪器（`dsh-compaction-tool-result-pruner`）只做确定性头/尾裁剪，不调用模型；
- spill（`dsh-spill` / `dsh-spill-policy`）：超大结果存文件，模型只拿有界预览 + 定位信息。

> 一句话：**上下文不是“聊天记录”，是一个有预算、有计量、有压缩策略的工程对象。**

---

## 5. 工具系统

### 5.1 工具定义

`dsh-tools` 的 `defineTool` 声明：

- 类型化参数与输出；
- 协作式超时（声明不等于强制，强制由 timeout-policy 包装层做）；
- 并行安全属性；
- UI 呈现意图（card）。

模型只看到 `name / description / parameter schema`；`execute`、`finalizeContent`、`timeoutMs` 不会泄漏到协议。

### 5.2 执行流水线

```
tools/pre-execute（允许/拒绝/询问）
  → 已注册单调守卫
  → tools/execute（环绕分发）
  → tools/post-execute（检查/替换/附加上下文）
  → finalizeContent（工具定义拥有）
  → tools/result（仅观测）
```

关键：**只有 `tools/execute` 视图可以替换信号**；`pre-execute` 不允许改写参数，
否则“记录的参数”和“实际运行的参数”会失去同步。

### 5.3 权限 / 审批 / 沙箱

- **权限预设**（`dsh-permission-presets`）：把“沙箱模式 + 审批策略”捆成具名模式；
  不匹配的组合显示为 `custom`。
- **审批**（`dsh-user-approval`）：一次性 `ask` / 直接拒绝 `never`；
  应答者缺失/失败 → `unavailable`，**拒绝关闭**；没有 `allow-always`。
- **沙箱**（`dsh-sandbox`）：`read-only` / `workspace-write` / `danger-full-access`；
  无法强制执行 → `SANDBOX_UNAVAILABLE`，**绝不静默放行**；
  被拒后可请求“严格更宽”模式，交由人工批准一次。
- **文件观察策略**（`dsh-fs-observation-policy`）：先读后写；
  文件自读取后变化 → 拒绝并提示重读；这是**事件门禁**，不是方法服务。

> 教学点：**工具是执行器，策略是门禁。** 工具不该自己判断“能不能写”，
> 它只请求防护；策略由独立插件决定。这样权限可以换、可以审计、可以测试。

### 5.4 后台任务

`dsh-jobs`：

- 每个 job 有 `<kind>-<short-uuid>`；
- 归属绑定 agent 会话，别的 agent 看不到/停不了；
- 有输出环、等待、取消、完成通知；
- `dsh-tool-bash` 的每条命令从启动起就是一个 job（`run_in_background` / 超时转后台）。

---

## 6. 多 Agent / 编排

### 6.1 Agent 与驱动分离

- `dsh-agent`：公开 `Agent` 接口 + 注册表；不创建模型请求。
- `dsh-agent-loop`：真正的 `ReactLoopAgent` 驱动器；通过工厂注册。
- 消费方依赖 `dsh-agent`，不依赖 `dsh-agent-loop` → 驱动器可替换。
- `AsyncLocalStorage` 把“发起方 Agent”带过异步调用，辅助函数不需要逐调用转发。

### 6.2 Subagent：一个服务，多个提供方

- `SubagentManager` 统一管理启动、消息准入、容量、父子关系、释放；
- 本地 **spawn / fork** 保留持久会话，可继续发消息；
- 外部后端（ACP、DSH SDK、Codex、Claude Code）执行一次，通过完成通知返回；
- 有深度限制；fork 继承父级模型/路由（为了 KV Cache 前缀复用）；
- 没有持久 parent mailbox：child 给 parent 发消息要求 parent 在线。

### 6.3 Workflow：模型写的 JS 编排脚本

- `agent()`、`parallel()`、`pipeline()`、`phase()`、`log()` 五个钩子；
- 前台执行，等待所有子 Agent；取消/异常返回错误，不返回部分成功；
- 没有 checkpoint；没有跨子 Agent 的 token 预算；没有嵌套 workflow；
- PTC 引擎在独立 Node 进程里跑，文件约束继承沙箱策略。

> 对比你的项目：你的 Router/Worker/Fan-out 是“手写编排”；
> DSH 把它抽象成“编排脚本 + 子 Agent 服务”。机制值得吸收，但**不要照搬 JS VM**。

### 6.4 Jobs / Schedule / Goal

- **Jobs**：后台任务，进程内注册表，按会话归属。
- **Schedule**：一次性/周期/每日/每周/cron，投递回原会话；宿主重启后仍可用。
- **Goal**：每个会话一个持久目标；create/edit/pause/resume/complete/block；
  `maxGoalRounds` 限制自动续行；**只存状态，不调度工作**。

> 这三个是“长任务”的三块拼图：后台执行、定时唤醒、跨轮目标。
> 你的项目目前只有“一轮内循环”，这块是明显空白。

---

## 7. Skill 系统

### 7.1 注册表 + 提供方

- `dsh-skill`：注册表，负责合并、重名裁决、验证、按需加载；
- `dsh-skill-filesystem`：本地提供方，扫描：
  - `<project>/.dsh/skills`
  - `<project>/.agents/skills`
  - `~/.dsh/skills`
  - `~/.agents/skills`
- 发现深度一层：`<name>/SKILL.md` 或 `<name>.md`；
- YAML frontmatter：`name`、`description`，可选 `whenToUse`、`metadata`、`disable-model-invocation`、`user-invocable`；
- 目录与正文分离：目录只放名称+描述；正文按需加载。

### 7.2 渐进披露（progressive disclosure）

- Agent 首次请求前拿到一份**持久目录**（名称 + 有长度上限的描述）；
- 需要时用 `skill` 工具加载正文；
- 用户可以用 `/name` 直接调用；
- 好处：不把所有技能正文塞进 prompt；目录小、正文按需。

> 你的项目已经有 `AGENTS.md` 和项目级 `.dsh/skills`；但 `ai-agent` 自己的 Python 运行时还没有“技能目录 + 按需加载”。
> 这是一个低成本、可教学化的吸收点。

---

## 8. LLM 层

### 8.1 Provider 无关

`dsh-llm`：

- 定义规范消息、内容块、流式分片词汇；
- 每个 provider adapter 只把自己的协议翻译成这套词汇；
- 一次流只尝试一次；重试由 `dsh-llm-retry` 在步骤边界做；
- 不提供缓存/限流；
- 请求深度冻结，Loop 构建的请求是会话日志的纯函数。

### 8.2 DeepSeek 适配器

`dsh-llm-deepseek`：

- Messages、推理、图片输入；
- 默认模型目录公布 **`deepseek-flash`**（不是 V4）；
- 不映射 `tool_choice`；
- 历史内 system 更新有排序约束；
- 图片是输入附件，不支持外部 URL / assistant 图片输出。

> 你提到“DeepSeek V4”：**当前这版 DSH 的默认目录里是 `deepseek-flash`**；
> V4 需要 provider/model 配置或适配器支持。可视化/吸收时不要把模型名写死。

---

## 9. 可观测性

- `dsh-otel`：普通事件 + Session 日志两个独立 OTLP 通道；每通道独立 exporter/resource/scope/队列；尽力而为，可能丢。
- `dsh-session-telemetry`：捕获有序会话副本，支持脱敏规则；交接非阻塞；崩溃可能丢队列。
- `dsh-session-stats`：全会话轮次/步骤/LLM/工具/首 token/解码墙钟；来自完整日志，压缩/分页不影响。

> 关键：**观测不是另装一套埋点，而是从同一份事件日志派生。**
> 你做可视化时也应该这样：动画读事件/投影，不要另写一套“猜测状态”的代码。

---

## 10. 设计原则（最值得学的）

1. **事件溯源**：先记录，再派生；模型可见即已记录。
2. **能力接口（seam）**：注册表 + 提供方；消费方依赖接口，不依赖实现。
3. **策略与机制分离**：工具执行 vs 权限门禁；FS 工具 vs 观察策略；沙箱 vs 审批。
4. **失败关闭**：沙箱不可用、审批不可用 → 拒绝，不静默放行。
5. **有界输出**：工具结果有预算；超大有 spill；上下文有 compression。
6. **渐进披露**：技能目录小、正文按需；AGENTS.md 按预算；压缩保留近期。
7. **显式生命周期**：owner、dispose、单写者、取消、结算。
8. **前台/后台显式**：workflow 前台；jobs 后台；schedule 宿主级；goal 只存状态。
9. **可替换驱动器**：Agent 接口与 Loop 实现分离。
10. **配置即组合**：profile/preset 决定装什么，而不是在代码里 if/else。

### 代价

- 包多、概念多、配置面大；学习曲线陡。
- 事件溯源要求“所有模型可见内容都可重建”，对插件作者是硬约束。
- 投影/压缩/持久化/权限的交互复杂，测试成本高。
- 对 5000 行的教学项目，**不能整套照搬**；只能吸收“契约与机制”。

---

## 11. 源码地图与阅读顺序

### 11.1 如果只读 3 个包

1. `dsh-agent-loop`：轮次/步骤/工具调度。
2. `dsh-session`：事件日志/surface/持久化语义。
3. `dsh-tools`：工具注册/执行流水线/权限门禁。

### 11.2 推荐顺序

| 顺序 | 包 | 看什么 |
|---|---|---|
| 1 | `dsh-agent-loop` | `src/agent.ts`（状态机）、`src/inbox.ts`、`src/tool-calls.ts` |
| 2 | `dsh-session` | `src/types.ts`（事件）、`src/surface.ts`（派生历史）、`src/repair.ts` |
| 3 | `dsh-session-persistence-jsonl` | `src/storage.ts`、`src/format.ts`、`src/generation.ts` |
| 4 | `dsh-session-projection` | `src/index.ts`（快照/变更） |
| 5 | `dsh-agent-instructions` | `src/files.ts`、`src/render.ts`、`src/state.ts` |
| 6 | `dsh-system-prompt` | `src/index.ts`（组装流水线） |
| 7 | `dsh-token-meter` | `src/estimate.ts`、`src/surface-fold.ts` |
| 8 | `dsh-compaction-basic` | `src/region.ts`、`src/summarizer.ts` |
| 9 | `dsh-tools` | `src/index.ts`（流水线）、`src/schema.ts` |
| 10 | `dsh-tool-fs` + `dsh-fs-observation-policy` | 读/写/编辑 + 先读后写 |
| 11 | `dsh-permission-presets` / `dsh-user-approval` / `dsh-sandbox` | 预设/审批/沙箱 |
| 12 | `dsh-subagent` | `src/manager.ts`、`src/activation.ts` |
| 13 | `dsh-workflow` / `dsh-workflow-ptc` | 脚本钩子、PTC 进程 |
| 14 | `dsh-skill` / `dsh-skill-filesystem` / `dsh-tool-skill` | 注册表/发现/按需加载 |
| 15 | `dsh-llm` / `dsh-llm-deepseek` / `dsh-llm-retry` | 流/适配/重试 |
| 16 | `dsh-otel` / `dsh-session-telemetry` | 上报/脱敏 |

---

## 12. DSH 不做什么（避免误读）

- **不是模型**：它不训练、不推理；推理在 LLM provider。
- **这套发行版里没有看到内置的向量长期记忆包**：会话日志 + 压缩 + 指令/技能，不是 RAG。
  你的 Chroma 记忆是**差异化优势**，不要为了“像 DSH”而丢掉。
- **没有 workflow checkpoint**：workflow 进程重启后不能续跑。
- **没有跨子 Agent token 预算**：workflow 限制并发/条目，但不统计 token。
- **没有 goal 调度**：goal 只存状态；续行由 `dsh-goal-round-driver` 等消费方决定。
- **没有 MCP prompts 模板**：MCP 工具/资源有，prompt 模板不支持。
- **审批没有 `allow-always`**：只有一次性授权。
- **沙箱只管文件**：不表达网络/进程/系统调用限制。
- **DeepSeek 适配器不映射 `tool_choice`**。

> 这些“没做”的地方，有些是你的机会：比如向量记忆、评测 rigor、教学可视化。

---

## 13. 对 ai-agent 的三条启示

1. **先把“事件日志”做出来**：它是可视化、回放、评测、恢复、成本的共同底座。
2. **把“策略”从工具里拆出来**：工具只执行；权限/审批/沙箱是独立门禁。
3. **不要复制体量，复制契约**：`Agent` 接口、`Tool` 接口、`Session` 事件、`Skill` 目录，
   这四个契约足够撑起下一阶段的深度。

具体怎么落到你的项目，见下一篇：[可吸收技术点与路线](可吸收技术点与路线.md)。
