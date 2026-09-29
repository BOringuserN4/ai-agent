# -*- coding: utf-8 -*-
"""
agent/rerank.py — 精排层（cross-encoder rerank）

2026/09/29 · 实战章 · rerank 层

=== 为什么需要它（技术背景）===

当前检索用**双塔（bi-encoder）**：查询与文档**分别编码**再比向量距离。
  · 优点：文档向量可**离线预计算** → 检索快
  · 致命缺陷：编码文档时**不知道谁会来查它**，且**查询与文档从不交互**
    → 字面重叠但意图不同的会被骗

实测反例（本模块的动机）：
  Q:「我那只英短叫什么名字」   ← 问的是**名字**
    #0 「用户的猫是一只英短，今年三岁」(0.6055)  ← 被"英短"骗走
    #1 「用户养了一只猫，名字叫豆豆」(0.5117)    ← 正确答案被压在下面

**交叉编码器（cross-encoder）**把查询与文档**拼在一起**送进模型，内部充分交互，
因此能分辨「问名字」与「提到品种」。但它**无法预计算** ——
检索 N 条要 N 次完整推理（1 万条：双塔几毫秒 vs 交叉上百秒，差 4 个数量级）。

于是业界标准是**两阶段**（retrieve-then-rerank）：
  阶段一 · 召回：双塔 + 向量库 → top-K（快、粗、宁可多带）
  阶段二 · 精排：交叉编码器逐条打分 → top-N（慢、准，但只有 K 条）

=== 本实现的三个关键决策 ===

1. **K 必须放宽**（召回条数 > 最终注入条数）
   因为 rerank **只能重排已召回的** —— 阶段一没捞到的，它救不了。
   所以要给足候选，让它有发挥空间。

2. **阈值改由 rerank 分数把关**
   rerank 分比向量分**更可信**（它看过原文），所以质量闸门放到这里；
   向量阶段只做"粗筛"、不设（或放宽）阈值。

3. **失败必须优雅降级**
   精排是**可选增强**，不是关键路径。服务不可用时应退回纯向量顺序，
   而不是让记忆检索整个失败。

=== 代价（值钱那行）===

  · **多一次网络往返**：K 条文档一次请求，实测 ~150-300ms
  · **成本按 K 线性增长**：K=20 与 K=50 差 2.5 倍（qwen3-rerank ¥0.5/百万 token）
  · **无法挽回漏召**：这是它的**天花板**
  · **会"帮倒忙"**：rerank 打错分时，会把**原本正确**的排到后面 ——
    所以必须实测，不能假设它一定更好
"""
import json
import os
import urllib.error
import urllib.request


# DashScope 的 rerank 端点是**独立**的（不是 OpenAI 兼容的那个 base_url）
RERANK_URL = ("https://dashscope.aliyuncs.com/compatible-api/v1/reranks")
DEFAULT_MODEL = "qwen3-rerank"


class DashScopeReranker:
    """阿里云百炼的 rerank（cross-encoder）。

    为什么用 HTTP 直调而不是 SDK：
      项目里没有 dashscope SDK 依赖（embedding 走的是 OpenAI 兼容端点），
      而 rerank 端点不在 OpenAI 兼容面里 → 直接 HTTP，零新增依赖。
    """

    def __init__(self, model: str = None, url: str = None, timeout: float = 30.0):
        self.model = model or os.getenv("RERANK_MODEL") or DEFAULT_MODEL
        self.url = url or os.getenv("RERANK_URL") or RERANK_URL
        self.timeout = timeout

    def _key(self) -> str:
        return os.getenv("DASHSCOPE_API_KEY", "")

    def rerank(self, query: str, documents: list, top_n: int = None) -> list:
        """对候选文档重排。

        Returns:
            [(原下标, relevance_score), ...]，按分数降序。
            失败时抛异常（调用方负责降级）。
        """
        if not documents:
            return []
        key = self._key()
        if not key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，无法调用 rerank")

        body = {"model": self.model, "query": query, "documents": documents}
        if top_n:
            body["top_n"] = min(top_n, len(documents))
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode())
        # 响应：{"results":[{"index":0,"relevance_score":0.93}, ...]}
        out = [(int(x["index"]), float(x["relevance_score"]))
               for x in (data.get("results") or [])]
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    def health(self) -> tuple:
        """探活：用一小段文本试一次。"""
        try:
            self.rerank("测试", ["测试文档"])
            return True, "ok"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"


class Reranker:
    """精排层的统一入口（带优雅降级）。

    对外只暴露一个方法：`apply(query, candidates)` →
    在 rerank 不可用时**原样返回向量顺序**，并标注 `reranked=False`。
    """

    def __init__(self, backend=None, enabled: bool = True):
        self.enabled = enabled
        self.backend = backend or DashScopeReranker()
        self.last_error = None

    def apply(self, query: str, candidates: list) -> list:
        """对候选重排。

        Args:
            query: 用户查询。
            candidates: 向量检索结果 [{text, score, meta}, ...]（顺序即向量排序）

        Returns:
            [{"text","score","meta","vector_score","reranked"}, ...]
              · score = 精排分（若成功）或原向量分（降级）
              · vector_score 始终保留原始向量分，便于对比与调试
        """
        base = [{"text": c["text"], "meta": c.get("meta", {}),
                 "vector_score": c.get("score", 0.0),
                 "score": c.get("score", 0.0), "reranked": False}
                for c in candidates]
        if not self.enabled or len(base) <= 1:
            return base

        try:
            ranked = self.backend.rerank(query, [c["text"] for c in base])
            if not ranked:
                return base
            out = []
            for idx, score in ranked:
                if 0 <= idx < len(base):
                    item = dict(base[idx])
                    item["score"] = round(score, 4)
                    item["reranked"] = True
                    out.append(item)
            # 兜底：若有候选没被 rerank 返回，补在后面（保持不丢）
            seen = {i for i, _ in ranked}
            out.extend(base[i] for i in range(len(base)) if i not in seen)
            self.last_error = None
            return out
        except Exception as e:
            # ⚠️ 优雅降级：精排是可选增强，不能拖垮记忆检索
            self.last_error = f"{type(e).__name__}: {e}"
            return base
