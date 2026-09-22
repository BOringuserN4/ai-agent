# -*- coding: utf-8 -*-
"""
agent/router_prefilter.py — Router 规则预筛（零 token 的路由判断）

编排章 · Router 成本优化，2026/09/22。

要解决什么：
  Router 是「LLM 判断要不要拆任务」，但它有**固定成本**——
  实测约 449 token/次（清掉工具声明后的值），而且**与任务难度无关**：
  一句「你好」也要付。这是「判断税」。

  → 本模块用**零 token 的规则**先拦一道：明显不用拆的，直接走 solo。

=== 为什么规则可以偏激进（本章最重要的判断）===

本项目里两种「误判」的后果**严重不对称**：

  | 误判 | 后果 | 有救吗 |
  | Router 误判「不拆」 | 降级（慢一点/贵一点） | ✅ solo 工具全开，接得住 |
  | 工具漏选 | 硬失败（工具不存在） | ❌ 只能重选 |

  所以：**宁可多判「不拆」，不可漏判「该拆」**——
  但即使漏判了，止损线是 solo 的能力上限，不会崩。

  ⚠️ 唯一例外是判据④「单 Agent 装不下」：那种情况 solo 会真失败。
     不过本项目任务都是短查询，触不到这条。

  ⇒ 结论：预筛只在**高置信度简单**时才跳过；不确定就交给 Router。

=== 判据（三条全满足才跳过）===

  1. **无多任务连接词**：出现「另外/同时/并且/再帮/顺便/两个都要」等 → 交 Router
  2. **命中意图组 ≤ 1 个**：复用「关键词 → 意图组」的分组思想（同 tool_selector）
  3. **无复杂度标记**：出现「开发/系统/项目/框架/架构/设计一个」等 → 交 Router

=== 代价（值钱那行）===

  - **关键词表要维护**：新说法要加词，漏了只是「退化成问 Router」，不会出错；
  - **会误判**：但方向安全（多判「不拆」而已），且可测量（见 eval 脚本）；
  - **少了一层 LLM 的"理解"**：规则不懂语义，只认词面。
    极端情况（如「把『今天天气很好』翻译成英文」里的「天气」）会被误当成天气意图——
    但后果同样安全：solo 照样能干。

  关键：**规则法的风险是"退化"，不是"崩溃"**——这与 tool_selector 的结论一致。
"""
import re

# ---- 多任务连接词：出现即认为「可能要多任务」，交 Router ----
# 说明：这些词意味着「同时要办两件以上」，正是 Router 擅长判断的场景。
MULTI_TASK_MARKERS = [
    "另外", "同时", "并且", "以及", "还有", "再帮", "再查", "再看",
    "顺便", "两个都", "都要", "分别", "各自", "第一", "第二",
    "然后", "接着", "既", "又",
]

# ---- 复杂度标记：出现即认为「可能很复杂」，交 Router ----
COMPLEXITY_MARKERS = [
    "开发", "实现一个", "搭建", "架构", "设计一个", "系统", "项目",
    "框架", "重构", "部署", "集成", "工作流", "流程", "多步", "步骤",
]

# ---- 意图组：查询命中哪个「专家职责」----
# 与 tool_selector 的思路一致：关键词 → 组。这里按「专家角色」分组，
# 而不是按「具体工具」分组（Router 关心的是派给谁）。
INTENT_GROUPS = {
    "math": {
        "keywords": ["算", "计算", "等于多少", "多少钱", "几加", "几乘",
                     "除以", "平均值", "总和", "+", "-", "*", "/", "×", "÷"],
    },
    "weather": {
        "keywords": ["天气", "气温", "温度", "下雨", "风速", "热不热",
                     "冷不冷", "多少度"],
    },
    "time": {
        "keywords": ["几点", "时间", "日期", "今天几号", "现在时刻"],
    },
}

# 跳过判据里的长度上限：过长（信息密集）的交 Router
MAX_SIMPLE_LEN = 60


class RouterPrefilter:
    """零 token 的路由预筛：决定「这条查询要不要问 Router」。"""

    def __init__(self, multi_markers=None, complexity_markers=None,
                 intent_groups=None, max_len=MAX_SIMPLE_LEN):
        self.multi_markers = multi_markers or MULTI_TASK_MARKERS
        self.complexity_markers = complexity_markers or COMPLEXITY_MARKERS
        self.intent_groups = intent_groups or INTENT_GROUPS
        self.max_len = max_len

    def _hit_groups(self, query: str) -> list:
        """查询命中了哪些意图组。"""
        q = query.lower()
        return [name for name, cfg in self.intent_groups.items()
                if any(kw.lower() in q for kw in cfg["keywords"])]

    def decide(self, query: str, explain: bool = False) -> tuple:
        """判断是否跳过 Router。

        Returns:
            (decision, reason)
              decision: "skip"（直接 solo，省一次 Router 调用）| "ask"（交 Router）
        """
        q = (query or "").strip()

        if not q:
            return "skip", "空输入"

        hit_multi = [m for m in self.multi_markers if m in q]
        if hit_multi:
            return "ask", f"含多任务连接词 {hit_multi}"

        hit_complex = [m for m in self.complexity_markers if m in q]
        if hit_complex:
            return "ask", f"含复杂度标记 {hit_complex}"

        if len(q) > self.max_len:
            return "ask", f"长度 {len(q)} > {self.max_len}（信息密集，交 Router）"

        groups = self._hit_groups(q)
        if len(groups) > 1:
            return "ask", f"命中 {len(groups)} 个意图组 {groups}（可能跨域，交 Router）"

        name = groups[0] if groups else "（无工具意图）"
        return "skip", f"单意图：{name}，无连接词/复杂度标记"


def decide_route(query: str, explain: bool = False) -> tuple:
    """便捷函数：用默认预筛器判断。"""
    return RouterPrefilter().decide(query, explain=explain)
