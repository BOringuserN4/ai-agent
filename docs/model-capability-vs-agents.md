# 番外篇 · 模型能力提升对 Agent 的影响

> 类型：文献综述（番外篇，非本项目实测）
> 日期：2026/10/06
> 方法：web 检索 8 组方向（综述 / 脚手架 / 多 Agent 失败 / 长时程退化 / 自更正 / 测试时计算 / 工具调用 / 记忆），
>       取一手来源（arXiv、ACL、NeurIPS、ICLR、厂商工程博客）。
> 严谨性约定：**每条结论标注证据强度**（强 / 中 / 弱）与**出处**；区分「论文实测」与「厂商/博客主张」；
>       本文件是**二手综述**，未逐篇复现，数字以原文为准。

---

## 0. 一句话结论

> **模型能力的提升，正在「吃掉」Agent 中那些「替模型补推理」的脚手架（planning / prompt-chaining / 复杂编排），
> 但「吃掉不了」那些与推理无关的维度：工具能力、上下文管理、信息获取、可验证性。**
> 两者是**不同轴**——「能力替代」与「脚手架持久」并非同一命题的两面，而常被混为一谈。

---

## 1. 问题的提出：一个被过度简化的直觉

流行的直觉是：

> 「模型越强 → 需要的 Agent 编排越少。」

这个直觉**部分成立，但作为整体命题是错的**。它混淆了两个轴：

| 轴 | 内容 | 模型变强的影响 |
|---|---|---|
| **推理轴** | 拆步、CoT、规划、自我批评、多轮反思 | **被吃掉**（模型内化了） |
| **工程轴** | 工具接入、上下文管理、外部信息、可验证性、隔离 | **不被吃掉**（非模型能力问题） |

**实证证据明确支持「分维度」而非「单调替代」**（见 §3–§5）。

---

## 2. 证据一：脚手架的两个「相反」结论（同一时期）

这是本主题最值得注意的**张力**——2025 年两篇高质量工作给出了**方向相反**的结论：

### 2.1 「简单即可，堆砌有害」

**More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding**（arXiv:2605.05716）【强】

- 全因子实验：5 个标准组件（Planning / Tool / Memory / Self-Reflection / Retrieval）的全部 **2⁵=32 种子集**，
  2 个基准（HotpotQA、GSM8K），3 个模型族 × 5 个规模。
- **核心发现**：
  - 最优组件数 **k\*=1–4**（依任务而定）；
  - **CCI（组件干扰）随能力递减**：8B 时「最优 vs 全上」差距 **32%**，70B 时 **19%**，
    到 Claude Haiku 级别 **≈0%（已在噪声内）**；
  - **Planning 的 Shapley 值显著为负**（φ=−0.029，95% CI 全在 0 以下）——
    即：**给任意组合加「规划」平均会降低表现**；
  - **Tool Use 占脚手架价值的 70%**。

> ⚠️ 该文同时**警告**：结论基于单模型代表每个 tier，不宜外推为普适定律。

### 2.2 「脚手架 > 模型」

**Confucius Code Agent**（arXiv:2512.10398）【强】

- SWE-Bench-Pro 公开集，**同一环境、同一模型**，只换脚手架：
  | 模型 | 脚手架 | Resolve@1 |
  |---|---|---|
  | Claude 4.5 Sonnet | SWE-Agent | 43.6 |
  | Claude 4.5 Sonnet | **CCA** | **52.7** |
  | Claude 4.5 Opus | 厂商私有脚手架 | 52.0 |
  | Claude 4.5 Opus | **CCA** | **54.3** |
  | GPT-5.2 | 厂商官方 | 56.0 |
  | GPT-5.2 | **CCA** | **59.0** |
- **结论句**：「即使**较弱的模型配上强脚手架**（Sonnet+CCA 52.7）也能**超过更强模型配弱脚手架**（Opus+私有 52.0）」。

### 2.3 如何调和这两个「相反」结论？

**关键在「测的是什么」**：

| | 2605.05716 | Confucius CCA |
|---|---|---|
| 任务 | **单跳/短程**（HotpotQA、GSM8K） | **长程、多文件**（SWE-Bench-Pro） |
| 脚手架本质 | 把「推理」外置（planning 等） | **工具/上下文/编排工程** |
| 结论 | 能力够了，**推理类脚手架有负收益** | **工程类脚手架**持续放大 |

> **调和命题**：模型能力**替代的是「推理类」脚手架**，**放大的是「工程类」脚手架的相对价值**。
> 两者不矛盾，因为测的是不同轴。

---

## 3. 证据二：脚手架敏感性是「非单调」的

**It's Not the Capability: Harness Sensitivity Is Non-Monotone Across LLM Agent Tiers**（arXiv:2605.26731）【中】

- 假设：能力越强 → 越不需要结构指导（单调反比）。
- **实测反驳该假设**：
  - harness 敏感性 **非单调**，且取决于**模型类型**（chat vs. reasoning）；
  - 对前沿推理模型（Qwen3.5-122B），**严格 harness 反而 +17pp 且降低延迟** ——
    与「高能力模型需要更少结构」**直接相反**；
  - chat 类模型：light ≈ balanced ≫ strict（严格结构反而有害）；
  - 「严格 harness 下延迟更低」（23.3s vs light 35.4s）——解释：显式成功标准**减少**了思考链长度。
- **局限**：每个 tier 只用一个模型代表 → 作者自己声明是「模型特定观察」，非普适规律。

> 该文最有价值的一点：**「能力↑ ⇒ 结构需求↓」这个流行假设，被实证证伪**（至少在特定模型/任务上）。

---

## 4. 证据三：多 Agent 的增益远不如宣传

**Why Do Multi-Agent LLM Systems Fail?**（MAST, arXiv:2503.13657, NeurIPS 2025）【强】

- 1642 条标注轨迹、7 个主流 MAS 框架、150 条精标（κ=0.88）。
- **核心数字**：MAS 在常见基准上**增益常常很小**；演讲版给出 **MAS 平均失败率 ~66%**。
- **失败分类学（MAST）**——14 种失败模式归入 3 大类：
  1. **规格问题**（specification）：违反任务/角色规格、步重复、对话丢失、不知终止条件；
  2. **Agent 间失配**（inter-agent misalignment）：信息扣留、忽略他人输入、任务跑偏、不复位；
  3. **任务验证**（task verification）：缺单元测试/多级验证。
- **关键归因**：失败**不只是底层模型能力的局限**——文中实测「模型局限」只解释约 **+9.4%**；
  更多来自**系统设计与角色规格**。

> 对应到本项目：**「多 Agent 是成本结构，买不到就别买」**这条铁律，与 MAST 的实证方向一致。

---

## 5. 证据四：长时程退化是「结构性」的

### 5.1 上下文位置效应

**Lost in the Middle**（Liu et al., TACL 2023）【强，经典】

- 性能在相关信息位于**开头/结尾**时最高，位于**中间**时显著下降；
- 极端时「中置答案」甚至**低于不给文档的闭卷基线**；
- 扩展上下文窗口的模型，**并未**更好利用上下文。

### 5.2 步数（而非窗口）是主因

**How Fast Do Agents Rot?**（arXiv:2609.01660）【中-强】

- 9 个模型（1.2B–671B）、4 类任务、5 个 horizon、3 种上下文制度。
- **任务成功率服从几何律**，由**单步可靠率 p** 支配；**p 随规模上升但饱和于 1 以下**
  → **长 horizon 崩溃是数学必然而非偶然**；
- **退化由「步数」而非「上下文长度」驱动**：**限制**上下文窗口反而**加剧**衰减
  （斜率 −0.69 vs −0.44，p=3×10⁻⁶）——**与 lost-in-the-middle 的解释相反**；
- 生产级模型在**仅 16 步**内崩塌于一个「它们几乎都能解」的任务。

> ⚠️ 该结论**挑战**了「上下文长度是主因」的通行说法；作者建议：**别把「压缩上下文」当出路**。

### 5.3 长时程诊断

**HORIZON**（arXiv:2604.11978）【中】：长时程失败模式——早期约束**仍在窗口内**却**不再被注意**
（effective inattention，而非字面遗忘）。

### 5.4 测试时扩展

**General AgentBench**（arXiv:2602.18998）【中】：从领域专项 → 通用 agent 设定，性能**普遍显著下降**
（如某些指标 58%→34%）；顺序 vs 并行 test-time scaling 各有天花板。

> ⇒ **长时程/通用化是当前 agent 的结构性弱点，且随模型变强改善有限。**

---

## 6. 证据五：自更正不是「免费的午餐」

**LLMs Cannot Self-Correct Reasoning Yet**（ICLR 2024）【强】

- **内在自更正**（无外部反馈）在推理任务上**无法**提升，**有时反而降低**性能。

**LLMs cannot find reasoning errors, but can correct them given the error location**（ACL Findings 2024）【强】

- 把自更正拆为「**找错**」与「**纠错**」两步：
  - **找错**是瓶颈（模型普遍不擅长）；
  - **纠错**能力强——**只要给出错误位置**，性能明显提升。

> **对本项目的直接含义**：
> ① 「self-critique 无脑套」不可信（呼应本项目 Evaluator-Critic 的实测教训）；
> ② 有效的自更正需要**外部信号/定位**——这恰是 **Agent 脚手架**的用武之地（提供验证、定位、工具反馈）。
> ⇒ **能力越强，也不能替代「外部可验证性」。**

---

## 7. 证据六：工具使用是当前的「价值中心」

- **工具价值占比**：Steering 全因子实验测得 **Tool Use 占脚手架价值 ~70%**（2605.05716）。
- **工具调用的真实短板**（WildToolBench, arXiv:2604.06185）【中】：
  - **多步工具调用准确率显著低于单步**；
  - 需要**澄清/反问**时，模型**常常误触发函数调用**；
  - 结论：有效工具使用不仅要求「会调工具」，还要求「理解用户」。
- **函数调用可工程改善**：Guided-Structured Templates（EMNLP 2025）等显示 3–12% 相对提升【中】。
- **工具数量与上下文开销**：MCP 等动态发现让工具 schema 吃 token（本项目已实测，见 `docs/mcp-basics.md`）。

> ⇒ 工具接入**不是**「模型强了就自动变好」的维度——它是**工程问题**，且是当前 agent 的主要价值来源。

---

## 8. 证据七：记忆与上下文管理长期仍是瓶颈

- **记忆综述**（Memory for Autonomous LLM Agents, arXiv:2603.07670）【强】：
  - 形式化为 **write–manage–read** 回路 + 三维分类（时间尺度 / 表征 / **控制策略**）；
  - **控制策略**（谁决定存/取/弃）是最关键也最少被讨论的维度；
  - 未解难题：持续巩固、因果检索、可信反思、**学会遗忘**。
- **越堆记忆越糟**：有研究指出**无限制扩张的记忆有害**（错误传播污染）【中，见 ACL 2026 记忆演化综述引述】。
- **窗口 ≠ 记忆**：Redis 工程博客主张「更大窗口不解决记忆」，**context rot**（随输入增长而不可靠）
  是自主的失败模式【弱-中，厂商博客，但与 5.1/5.2 一致】。

> ⇒ 记忆/上下文管理是**工程轴**，模型变强**不自动解决**。

---

## 9. 综合：模型能力提升对 Agent 的「分维度」影响

| 维度 | 模型变强的影响 | 证据强度 | 关键出处 |
|---|---|---|---|
| **推理/规划（外置）** | ⬇️ **被替代**；堆 planning 甚至负收益 | 强 | 2605.05716 |
| **自更正（内在）** | ➡️ 仍弱；需外部定位/反馈 | 强 | ICLR'24; ACL'24 |
| **工具使用** | ⬆️ 改善但仍需工程；占价值 70% | 强-中 | 2605.05716; WildToolBench |
| **上下文/记忆管理** | ➡️ 不自动解决；越堆越糟风险 | 强 | 2603.07670; lost-in-middle |
| **长时程可靠性** | ⬆️ 随规模升但**饱和**；几何崩溃 | 中-强 | 2609.01660; MAST |
| **多 Agent 编排** | ➡️ 增益常被高估；失败率 ~66% | 强 | MAST (NeurIPS'25) |
| **工程脚手架** | ⬆️ 相对价值**上升** | 强 | CCA (2512.10398) |
| **结构敏感性** | 🔄 **非单调**，依模型类型 | 中 | 2605.26731 |

**读法**：
- ⬆️ = 模型变强**放大/改善**该维度；
- ⬇️ = 模型变强**替代**该维度；
- ➡️ = 模型变强**基本无影响**（仍需工程）；
- 🔄 = 无单调规律。

---

## 10. 对本项目（`~/ai-agent`）的印证与修正

本项目的**实测**与上述文献**方向一致**：

| 本项目实测 | 对应文献 | 关系 |
|---|---|---|
| 显式规划「实测否决」（小任务无病、长链救不了）| **Planning Shapley 负值**（2605.05716）| ✅ 独立印证 |
| 层级编排：慢工具下并行省 61–76%，快工具纯负债 | 脚手架价值**条件性** | ✅ 一致 |
| 去中心化：信息分散时集中式 33% vs 100% | **信息获取是工程轴** | ✅ 一致 |
| Evaluator-Critic：自己批自己撞自我确认 | **内在自更正无效**（ICLR'24）| ✅ 独立印证 |
| 「多 Agent 是成本结构」铁律 | **MAST 失败率 ~66%** | ✅ 一致 |

**文献补充的新认知（本项目此前未覆盖）**：
1. **「能力↑ ⇒ 结构需求↓」是非单调的**（2605.26731）——比本项目「条件性必要」更锋利；
2. **长时程崩溃由「步数」而非「上下文长度」驱动**（2609.01660）——影响未来的上下文策略；
3. **工具价值占脚手架 ~70%**（2605.05716）——为「工具优先」提供量化依据。

---

## 11. 诚实边界（严谨性声明）

1. **本文件是二手综述**，未逐篇复现实验；数字与结论以原文为准，可能存在引述偏差。
2. **多个来源时效极新**（arXiv 2026 编号，如 2605.x / 2609.x / 2603.x），
   引用前**建议核对原文版本**；部分为预印本，**未经同行评审**。
3. **部分结论有明确局限**：
   - 2605.05716 / 2605.26731 均声明「每 tier 单模型代表」→ **不宜外推**；
   - 2609.01660 的「步数而非长度」结论**挑战**通行解释，尚待更广复现。
4. **厂商来源**（Anthropic、Redis、GitHub 博客）标为【弱-中】，与论文证据分级对待；
   Anthropic 的「多 Agent 提升 90.2%」为其**内部研究**，无同行评审，**不应作为定论**。
5. 「能力替代 vs 脚手架持久」的调和命题（§2.3）是**本文件的综合判断**，非任一原文的直接结论。

---

## 12. 参考文献（按主题）

**综述**
- Wang et al. *A Survey on LLM-based Autonomous Agents*. arXiv:2308.11432（v7, 2025）
- Mohammadi et al. *Evaluation and Benchmarking of LLM Agents: A Survey*. KDD'25, arXiv:2507.21504
- Mei et al. *A Survey of Context Engineering for LLMs*. arXiv:2507.13334（166 页, 1411 引用）
- *Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers*. arXiv:2603.07670
- Zhang et al. *A Survey on the Memory Mechanism of LLM-based Agents*. arXiv:2404.13501

**脚手架 / 能力替代**
- *More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding*. arXiv:2605.05716
- *Confucius Code Agent*. arXiv:2512.10398
- *It's Not the Capability: Harness Sensitivity Is Non-Monotone Across LLM Agent Tiers*. arXiv:2605.26731
- Xia et al. *Agentless: Demystifying LLM-based Software Engineering Agents*. arXiv:2407.01489 / FSE'25

**多 Agent 失败**
- Cemri et al. *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657, NeurIPS'25 (MAST)

**长时程 / 上下文**
- Liu et al. *Lost in the Middle: How Language Models Use Long Contexts*. TACL 2023
- *How Fast Do Agents Rot?* arXiv:2609.01660
- *The Long-Horizon Task Mirage?* (HORIZON) arXiv:2604.11978
- *Benchmark Test-Time Scaling of General LLM Agents*. arXiv:2602.18998

**自更正**
- Huang et al. *LLMs Cannot Self-Correct Reasoning Yet*. ICLR 2024
- Tyen et al. *LLMs cannot find reasoning errors, but can correct them given the error location*. ACL Findings 2024
- Kamoi et al. *When Can LLMs Actually Correct Their Own Mistakes?* TACL 2024

**工具使用**
- *Benchmarking LLM Tool-Use in the Wild* (WildToolBench) arXiv:2604.06185
- *ACEBench* EMNLP Findings 2025; *Meta-Tool* ACL 2025

**测试时计算**
- *Learning When to Plan: Efficiently Allocating Test-Time Compute for LLM Agents*. arXiv:2509.03581
- Ji et al. *A Survey of Test-Time Compute*. arXiv:2501.02497

**厂商 / 工程博客**（证据级【弱-中】）
- Anthropic, *Building Effective Agents*（2024-12）; *Effective context engineering for AI agents*（2025-09）
- Redis, *Why a Bigger Context Window Won't Fix Agent Memory*
