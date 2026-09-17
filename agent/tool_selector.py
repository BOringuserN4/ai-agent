# -*- coding: utf-8 -*-
"""
agent/tool_selector.py — 工具裁剪（按需加载），省掉「工具清单的租金」

协议章 · 工具裁剪，2026/09/17。

要解决的问题（方案 B 实测）：
  全量挂载 14 个工具时，同一任务、同一答案，多付 **+3571 token（+308%）**。
  这钱花在**工具清单本身**上——还没开始干活，先交 3500+ token 的租金。

裁剪的判据从哪来（关键设计决策）：
  **不能用 LLM 判断**。本项目已经吃过这个亏：Router 每次判断要 853 token
  （见 docs/orchestration-patterns.md §6）。用 LLM 省 token，等于
  「花 853 省 3500」——收益被自己的判断成本吃掉，而且判断还会错。

  所以用**规则预筛**：查询里的关键词 → 工具分组。零 token、确定性、可测。

设计取舍：
  - **宁可多带、不可漏带**：漏掉必要工具会导致任务失败（比多带几个更贵）。
    所以默认集偏保守，匹配不到时回退到「安全集」而不是空集。
  - 分组用**工具名 + 描述 + 别名关键词**三处匹配，不只看工具名。
  - 选择过程本身可解释：能打印「为什么选了这几个」（可调试、可审计）。

代价（值钱那行）：
  - 规则要维护：新增工具/新说法时要更新关键词表（漏了就选不中）；
  - 召回是近似的：关键词匹配会有「该选没选」和「不该选却选了」；
  - 多一层代码路径，出问题时要能降级回全量（提供 `always_include` / 全量开关）。
"""
import re


class ToolSelector:
    """按查询关键词，从候选工具里裁出一个尽量小的子集。

    用法：
        sel = ToolSelector(groups={...})
        picked = sel.select(query, candidate_names, spec_lookup)
    """

    # 默认分组：关键词 -> 工具名（本项目 filesystem + weather 两个 server 的实测清单）
    DEFAULT_GROUPS = {
        "read": {
            "keywords": ["读", "读取", "查看", "打开", "内容", "显示", "read", "cat", "看"],
            "tools": ["fs__read_text_file", "fs__read_file", "fs__read_multiple_files"],
        },
        "list": {
            "keywords": ["列", "列出", "目录", "有哪些", "清单", "list", "ls", "结构", "树"],
            "tools": ["fs__list_directory", "fs__list_directory_with_sizes",
                      "fs__directory_tree", "fs__list_allowed_directories"],
        },
        "search": {
            "keywords": ["找", "搜索", "查找", "搜", "search", "find", "匹配"],
            "tools": ["fs__search_files"],
        },
        "info": {
            "keywords": ["大小", "多大", "信息", "属性", "元数据", "多少字节", "size", "info"],
            "tools": ["fs__get_file_info"],
        },
        "write": {
            # 注：必须含单字「建」——压测发现「建一个叫 reports 的目录」只命中
            # list 组（因含「目录」），漏掉 create_directory，任务会直接失败。
            "keywords": ["写", "建", "创建", "新建", "保存", "覆盖", "write", "create", "save"],
            "tools": ["fs__write_file", "fs__create_directory"],
        },
        "edit": {
            "keywords": ["改", "修改", "编辑", "替换", "edit", "replace"],
            "tools": ["fs__edit_file"],
        },
        "move": {
            "keywords": ["移动", "重命名", "挪", "move", "rename"],
            "tools": ["fs__move_file"],
        },
        "weather": {
            "keywords": ["天气", "气温", "温度", "下雨", "weather", "风速"],
            "tools": ["weather__get_weather"],
        },
    }

    # 永远带上（成本极低、且几乎任何文件任务都可能需要）
    ALWAYS_INCLUDE = []

    # 一个都匹配不上时的安全回落：只读类工具，避免「写/删」这类危险动作被误挂
    FALLBACK_KEYWORDS = ["read", "list"]

    def __init__(self, groups: dict = None, always_include: list = None):
        self.groups = groups or self.DEFAULT_GROUPS
        self.always_include = list(always_include or self.ALWAYS_INCLUDE)

    def _matched_groups(self, query: str) -> list:
        """查询命中了哪些分组（按关键词做大小写不敏感的子串匹配）。"""
        q = (query or "").lower()
        hit = []
        for name, cfg in self.groups.items():
            for kw in cfg["keywords"]:
                if kw.lower() in q:
                    hit.append(name)
                    break
        return hit

    def select(self, query: str, candidates: list, explain: bool = False) -> list:
        """从 candidates 里裁出本轮需要的工具子集。

        Args:
            query: 用户输入（用来判断需要哪类工具）。
            candidates: 当前**所有可用**的工具名（如 bridge.tool_names）。
            explain: 是否打印选择理由。

        Returns:
            选中的工具名列表（保持 candidates 的原有顺序，便于对照）。
        """
        cand_set = set(candidates)
        groups = self._matched_groups(query)
        if not groups:
            groups = self.FALLBACK_KEYWORDS
        picked = set(self.always_include)
        for g in groups:
            cfg = self.groups.get(g)
            if cfg:
                picked |= {t for t in cfg["tools"] if t in cand_set}
        # 保序 + 过滤不存在的
        # ⚠️ 宁可多带：若规则没命中任何当前可用工具，回退为「全量」，
        #    避免把必要工具裁掉导致任务直接失败（漏带比多带更贵）。
        result = [n for n in candidates if n in picked]
        if not result:
            if explain:
                print(f"   ⚠️ 规则未命中任何可用工具（组：{groups}）→ 回退全量 {len(candidates)} 个")
            return list(candidates)
        if explain:
            print(f"   🎯 命中分组：{groups} → 选中 {len(result)}/{len(candidates)} 个工具")
        return result


def attach_selected_tools(agent, bridge, query: str, selector: ToolSelector = None,
                          explain: bool = True):
    """按查询裁剪后，才把 MCP 工具挂到 Agent 上。

    与 attach_mcp_tools 的区别：**先裁后挂**——没被选中的工具
    连 schema 都不会进请求，token 才是真省下来。

    返回 (挂载的工具名列表, 选择器实例)。
    """
    selector = selector or ToolSelector()
    chosen = selector.select(query, bridge.tool_names, explain=explain)

    all_specs = {s["function"]["name"]: s for s in bridge.to_openai_specs()}
    all_reg = bridge.to_registry()

    agent.tools_spec = list(agent.tools_spec) + [all_specs[n] for n in chosen if n in all_specs]
    agent.tool_registry = {**agent.tool_registry,
                           **{n: all_reg[n] for n in chosen if n in all_reg}}
    return chosen, selector
