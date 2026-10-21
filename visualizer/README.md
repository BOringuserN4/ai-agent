# Agent Replay · P1/P2 原型

> 把一次 Agent 运行回放成一张**时序图**：User / LLM+Context / Tools / Memory / Extractor 五条生命线，消息逐条展开。
> 不是监控看板，是教学回放器；支持三套真实 trace：开发小工具 / 完整 Agent / 最小 Agent。

## 先看效果

```bash
open visualizer/index.html
```

页面右上角有两组切换：

- **VIEW：时序 / 结构**（默认时序）
- **DEMO：开发：写脚本 + 运行**（默认）
- **完整：记忆 + 2 工具 + Extractor/Guard**
- **最小：1 工具**

`时序` 是主视图，逐条消息播放；`结构` 是静态模块地图，只按当前步骤高亮
模块和连线，不播放 packet。切换视图不会丢当前 step。

## 开发示例：统计数据小工具

任务：

> 帮我写一个统计数据的小工具：读取 sales.csv，按 category 统计 count/sum/avg，按我的偏好输出；先写文件，再运行验证。

真实 trace：

| 模块 | 这次发生了什么 |
|---|---|
| **Memory** | 召回用户偏好“统计结果用 JSON 输出”（0.597） |
| **Tools** | `read_file` 读 CSV → `write_file` 写 `stats_tool.py` → `run_python` 运行 |
| **Guard** | `max_steps=3`，剩 2/1 步时各预警一次 |
| **Extractor** | 待命（这次没有写记忆） |
| **LLM** | 3 次调用：读文件 → 写脚本 → 运行后回答 |
| **结果** | 运行 `exit_code=0`，输出 A/B/C 的 count/sum/avg JSON |

- **20 条事件**；
- 3 个工具调用；
- 4596 tokens。

页面重点看：

1. Memory 召回偏好后，system prompt 里多出“JSON 输出”；
2. LLM 先 `read_file` 看数据，再 `write_file` 写脚本；
3. 第二轮 `run_python` 真跑脚本，`stdout` 回流；
4. 第三轮带着真实输出作答；
5. Guard 在剩 2 步/1 步时预警。

## 完整示例覆盖了什么

任务：

> 我的职业是什么？请先算 123 * 456，再查上海现在的时间，然后结合我的职业，用一句话总结。

真实 trace：

| 模块 | 这次发生了什么 |
|---|---|
| **Memory** | 检索命中 **2 条**（职业/学习 Agent）；最高分 **0.648** |
| **Tools** | `calculator` → 56088；`current_time` → 上海时间 |
| **Extractor** | 回答后判断 `keep=true`，写入 1 条职业记忆 |
| **Guard** | `max_steps=2`，第 1 步后剩 1 步，触发“尽快收尾”预警 |
| **LLM** | 2 次调用；Agent 共 **1391 tokens** |

这条 trace 有 **15 条事件**。页面里可以直接看到：

1. 记忆先召回，再注入 system prompt；
2. 两个工具在同一轮被调用，结果回流；
3. 预算变紧，第二步只作答；
4. 回答后 Extractor 判断 keep，再写入 Memory；
5. Tracer / Judge 等旁路模块在底部，不阻塞主链。

## 最小示例

任务：

> 请用 calculator 工具计算 123 * 456，不要心算。

- 10 条事件；
- 2 次 LLM；
- 1 次工具；
- 902 tokens。

## 布局：时序图

中间是五条生命线：

```text
USER          LLM + CONTEXT          TOOLS        MEMORY       EXTRACTOR
 │  task ───────────▶│
 │                   │◀── recall 1 ──────────────│
 │                   │── read_file ──▶│
 │                   │◀── CSV 6 行 ──│
 │                   │── write_file ─▶│
 │                   │◀── wrote 2130c │
 │                   │── run_python ─▶│
 │                   │◀── exit 0 ─────│
 │◀──── answer ──────│
```

- **User**：任务与最终回答；
- **LLM + Context**：模型 + 上下文，所有请求/响应都落在这条线上；
- **Tools**：`read_file` / `write_file` / `run_python`；
- **Memory**：召回偏好；写入走 Extractor；
- **Extractor**：`memory_write` 时出现 `keep` / `store` 两行。

时间从上往下走：每条消息是一条水平线，当前消息变蓝、终点亮起，
未发生的消息保持淡色；Guard 是黄色 note，Tracer/Judge/MCP 在底部旁路条。
**没有箭头**，方向由生命线和消息起止表达。

点顶部 `结构` 切到静态模块地图：LLM+Context / Tools / Memory / Answer /
Extractor 的拓扑关系，当前步骤只高亮相关模块和连线；再点 `时序` 回到播放视图。

## 页面怎么用

- 点 **▶** 播放，**⏸** 暂停；
- **← / →** 单步；
- 拖底部进度条，跳到任意事件；
- 点左侧事件，看那一刻的 payload；
- 右上角切换 `完整 / 最小`；
- 右侧“这一刻”是原始 JSON + 一句人话解释。

## 文件

```text
visualizer/
├── index.html          # 单文件回放页（三套 trace 已内嵌）
├── template-seq.html   # 时序图 + 结构图模板（当前）
├── template.html       # 旧架构图模板（保留，不再构建）
├── build.py            # trace*.jsonl → index.html
├── record_minimal.py   # 录最小 Agent
├── record_full.py      # 录完整 Agent（记忆/2 工具/预算/Extractor）
├── record_dev.py       # 录开发示例（读 CSV / 写脚本 / 运行）
├── trace.jsonl         # 最小示例
├── trace_full.jsonl    # 完整示例
└── trace_dev.jsonl     # 开发示例
```

## 重新录

```bash
# 最小
.venv/bin/python visualizer/record_minimal.py "请用 calculator 工具计算 123 * 456，不要心算。"

# 完整（会调 embedding / extractor / 2 个工具，费用比最小大）
.venv/bin/python visualizer/record_full.py

# 开发示例（会读写临时目录 + 运行 Python）
.venv/bin/python visualizer/record_dev.py

# 重新生成页面
.venv/bin/python visualizer/build.py
open visualizer/index.html
```

三套脚本都会真实调用 API；trace 里不包含 key。

## 事件流

```text
run_start
memory_search          # 命中 2 条
context_built          # system + 记忆 + user
llm_request
llm_response           # 同时调 calculator + current_time
budget_warning         # 剩 1 步
tool_call / tool_result × 2
context_built          # 工具结果进入 history
llm_request
llm_response           # 最终回答
memory_write           # extractor 沉淀
run_end
```

## 这一版故意不做什么

- 不做实时（先回放；实时需要 SSE/背压/重连）；
- 不做多 Worker 并行（当前 trace 是单 Agent；Fan-out 分支放下一版）；
- 不画模型内部（只画 API 输入输出，不假装看神经元）；
- 不做 3D/WebGL；
- 不把 UI 逻辑塞进 `agent/`（`agent/` 只 emit 事件）。

## 下一步

- P2+：多 Worker 并行时，画 2 条 Worker 分支 + Fan-in；
- 加 EC / 预算耗尽 / 工具失败的红色断点；
- 两次运行对比（加记忆 vs 不加、solo vs 拆）；
- 可选：实时模式、导出 GIF/MP4。

> 先看这 15 条事件能不能讲清：
> 记忆有没有用、两个工具怎么回流、预算怎么让 Agent 收尾、Extractor 写了什么。
