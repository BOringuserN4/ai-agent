# -*- coding: utf-8 -*-
"""
agent/memory.py — 长期记忆（LTM）模块（RAG 实现，ChromaDB 版本）

核心思路：
  - 记忆不塞进对话 history（否则上下文会爆炸），而是「外置存储 + 按需检索」。
  - 每条记忆 = 文本片段 + 语义向量 + 元数据。
  - 写入：对话产生的重要信息，通过远程 embedding 生成向量后存入 ChromaDB。
  - 检索：用户提问时，用远程 embedding 生成查询向量，交给 ChromaDB 做近似最近邻（HNSW）检索，取 top-k 注入上下文。

技术栈：
  - embedding 后端**可插拔**（2026/09/19）：云端 DashScope text-embedding-**v4**（现状）或
    局域网 Ollama（Qwen3-Embedding-0.6B），见 agent/embedding_backends.py。
    （注：本地推理后端 2026/09/19 已停用，当前默认云端；v3→v4 于 2026/09/29 完成。）
    用环境变量 EMBEDDING_BACKEND=dashscope|ollama 切换，默认 dashscope。
    ⚠️ 两个后端的向量**不可混用**，故各自用独立的 ChromaDB collection。
  - ChromaDB：本地向量数据库（PersistentClient 持久化），内置 HNSW 索引，
    把之前的「numpy 暴力点积检索（O(N)）」升级为「索引近似最近邻（O(log N)）」。

价值：
  - 跨会话记住用户偏好、历史事实。
  - 不占上下文窗口：只取相关片段，而非全量携带。
  - 规模化：记忆条目增长到几千/几万条时，检索依然快速，不再线性遍历。

对外 API（与旧版完全一致，core.py / multi_agent.py 无需改动）：
  - add(text, meta)   写入一条记忆（文本哈希去重）
  - search(query, top_k) 语义检索，返回 [{text, score, meta}]
  - count() / clear() / all_texts()
"""
import os
import hashlib
from dotenv import load_dotenv
from agent.embedding_backends import get_backend

load_dotenv()

# 召回阈值（2026/09/29 由 0.6 下调到 0.46）
# 依据：把「自然口语问法」纳入评测后重新推导——
#   v3@1024 合并空档只有 +0.0116（几乎分不开），v4@1024 为 +0.0653；
#   v4 下的推荐区间是 (0.4274, 0.4927]，取中点附近 0.46。
#   旧的 0.6 是在「只含标准措辞」的语料上定的，遇到自然问法必然漏召。
# 可用环境变量 MEMORY_MIN_SCORE 覆盖。
MIN_SCORE = float(os.getenv("MEMORY_MIN_SCORE") or 0.46)

# 精排（cross-encoder rerank）开关 —— **默认关闭**。
# 实测（2026/09/29，40 条语料 / 15 用例）：开启后 Top-1 由 14/15 降到 13/15，
# 且延迟 +306ms（206 → 513ms）。原因是两者失败模式不同：
#   · 双塔被「词面重叠」骗（问"英短叫什么" → 选到品种那条）
#   · rerank 被「俚语/生词」骗（问"主子叫什么" → 选到"领导叫李工"那条）
# 故当前向量检索（v4 + 增富 + 0.46 阈值）已够用，精排留作**可选增强**。
# 需要时设 RERANK_ENABLED=1 打开；也可配合 RERANK_TOP_K 放宽召回。
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "").lower() in ("1", "true", "yes")
# 开启精排时，阶段一要多召回候选（rerank 救不回漏召，故须给足）
RERANK_RECALL_K = int(os.getenv("RERANK_RECALL_K") or 20)

# ChromaDB 持久化目录（运行时生成，含用户信息，不入库）
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_data")
COLLECTION_NAME = "memory_store"


class MemoryStore:
    """基于 ChromaDB 的长期记忆仓库：持久化 + HNSW 语义检索。"""

    def __init__(self, top_k=8, backend=None, chroma_dir=None):
        """
        Args:
            top_k: 检索条数上限。
            backend: 可选的 embedding 后端实例（见 agent/embedding_backends.py）。
                     不传则按环境变量 EMBEDDING_BACKEND 取（默认云端 DashScope）。
            chroma_dir: 可选，覆盖向量库目录（评测用独立目录，不碰真实记忆）。
        """
        self.top_k = top_k
        # 精排层（默认关闭；见文件头 RERANK_ENABLED 的实测说明）
        self.reranker = None
        if RERANK_ENABLED:
            try:
                from agent.rerank import Reranker
                self.reranker = Reranker(enabled=True)
            except Exception:
                self.reranker = None      # 依赖缺失不影响主流程
        # 可插拔后端：默认仍是云端（不改变既有行为）
        self.backend = backend or get_backend()
        self.chroma_dir = chroma_dir or CHROMA_DIR
        # 不同后端的向量**不可混用** → collection 名按后端区分，避免混表。
        # 注意：后端可能带**自动回退**（本地挂了退云端），此时实际生效的后端
        # 会在运行时变化，所以 collection 不能只在构造时定死 ——
        # 每次读写前用 _sync_collection() 校正。
        self._ensure_chroma()
        self._sync_collection(initial=True)

    def _space_id(self) -> str:
        """当前向量空间的标识：后端 + 模型 + 维度。

        为什么必须包含模型与维度（2026/09/29 修正）：
          原先只按后端名（dashscope / ollama）区分集合 —— 但**同后端内换模型
          同样是换向量空间**。换模型后若沿用同一集合，新旧向量会混表，
          检索结果静默崩坏（分数看着正常，实际是两种空间的混算）。
          这是 skill「embedding-backend-swap」明确警告的失败模式。

        兼容：legacy 组合（dashscope + text-embedding-v3 + 1024）仍映射到
        原名 `memory_store`，既有数据不受影响、无需迁移。
        """
        b = self.backend
        model = getattr(b, "model", "") or ""
        dim = getattr(b, "dim", None)
        if b.name == "dashscope" and model == "text-embedding-v3" and dim == 1024:
            return COLLECTION_NAME            # legacy：保持原名
        parts = [COLLECTION_NAME, b.name]
        if model:
            parts.append(model.replace(".", "-"))   # 点号不合集合命名惯例
        if dim:
            parts.append(str(dim))
        return "_".join(parts)

    def _sync_collection(self, initial: bool = False):
        """让 collection 与**当前实际生效**的后端保持一致。

        回退还意味着「换了一个向量空间」，所以必须同时换表。
        这一步若漏掉，两种向量会混进同一张表，检索结果静默崩坏。
        """
        want = self._space_id()
        if getattr(self, "collection_name", None) == want:
            return
        prev = getattr(self, "collection_name", None)
        self.collection_name = want
        self.collection = self._chroma.get_or_create_collection(
            name=want, metadata={"hnsw:space": "cosine"},
        )
        if not initial and prev:
            print(f"   🔀 embedding 后端切换（{prev} → {want}），已切到对应的向量集合")

    # ---- ChromaDB 持久化 ----
    def _ensure_chroma(self):
        """初始化 ChromaDB 客户端 + 集合（首次使用时创建）。"""
        import chromadb
        # PersistentClient：数据写到磁盘，跨进程重启后还在。
        self._chroma = chromadb.PersistentClient(path=self.chroma_dir)
        # collection 的创建延后到 _sync_collection()，因为后端可能带自动回退、
        # 实际生效的后端要到运行时才确定。

    # ---- embedding（委托给可插拔后端，归一化在后端内统一做）----
    def _embed(self, texts):
        """把文本转成向量。后端可插拔（云端 DashScope / 本地 Ollama）。

        支持：
          - texts 是 str  → 返回单个向量（一维数组）
          - texts 是 list → 返回 (N, dim) 矩阵
        """
        return self.backend.embed(texts)

    # ---- 写入记忆 ----
    def add(self, text: str, meta: dict = None, embed_text: str = None):
        """添加一条记忆：向量化 + 存储。使用文本哈希去重。

        Args:
            text: **注入上下文用**的文本（保持简洁，省 token）。
            meta: 元数据。
            embed_text: **向量化用**的文本，可带「问法提示」等增富内容。
                不传则与 text 相同（向后兼容）。

        为什么要分开（2026/09/29）：
            检索质量取决于「记忆向量」与「问句向量」的接近程度。实测发现，
            把记忆文本改写成「事实 + 可能被怎么问」，能显著拉高召回分且
            **不抬高无关记忆的分数**（见 docs/03-实战章/memory-recall-fix.md）。
            但增富后的文本若直接注入上下文，会白吃 token ——
            所以拆成两份：**向量化用增富版，注入用精简版**。
        """
        text = text.strip()
        if not text:
            return
        self._sync_collection()          # 后端可能已回退 → 先对齐集合
        # 去重：同文本不重复存（用 md5 作为唯一 id）
        digest = hashlib.md5(text.encode()).hexdigest()
        # 先查 id 是否已存在，避免重复写入导致的重复检索
        exists = self.collection.get(ids=[digest])
        if exists and exists.get("ids"):
            return
        # 向量化：优先用增富文本（embed_text），存储仍用精简文本（text）
        vec = self._embed(embed_text if embed_text else text)
        self.collection.add(
            ids=[digest],
            documents=[text],
            embeddings=[vec.tolist()],
            metadatas=[meta or {"type": "manual"}],
        )

    # ---- 检索记忆 ----
    def search(self, query: str, top_k: int = None, min_score: float = None):
        """
        语义检索：返回最相关的若干条记忆。
        Returns: list of {text, score, meta}
        """
        self._sync_collection()          # 后端可能已回退 → 先对齐集合
        if self.collection.count() == 0:
            return []
        if min_score is None:
            min_score = MIN_SCORE        # 见文件头 MIN_SCORE 的说明
        top_k = top_k or self.top_k
        q_vec = self._embed(query)  # str 单条
        # 开启精排时**放宽召回**：rerank 只能重排已召回的，所以要给足候选。
        recall_k = max(top_k, RERANK_RECALL_K) if self.reranker else top_k
        # ChromaDB query：返回最近的 recall_k 条，带 distance。
        res = self.collection.query(
            query_embeddings=[q_vec.tolist()],
            n_results=recall_k,
        )
        # 取第一个 query 的结果
        docs = res.get("documents") or [[]]
        metas = res.get("metadatas") or [[]]
        dists = res.get("distances") or [[]]
        result = []
        for doc, meta, dist in zip(docs[0], metas[0], dists[0]):
            # cosine 距离越小越相似；转成相似度分数 score = 1 - distance
            score = 1.0 - float(dist) if dist is not None else 0.0
            if score < min_score:
                continue
            result.append({
                "text": doc,
                "score": round(score, 4),
                "meta": meta or {},
            })
        # 可选精排：失败时内部自动降级为原向量顺序（不影响可用性）
        if self.reranker and result:
            result = self.reranker.apply(query, result)
            # 精排后按精排分再过滤一次（分数口径已换成 rerank 分）
            result = [r for r in result if r.get("score", 0) >= min_score]
            return result[:top_k]
        return result

    # ---- 工具方法 ----
    def count(self) -> int:
        return self.collection.count()

    def clear(self):
        """清空全部记忆。ChromaDB 1.5+ 的 delete(where={}) 会抛 ValueError，
        改为「先取全部 id，再按 id 删除」，兼容性好。
        """
        ids = self.collection.get().get("ids", [])
        if ids:
            self.collection.delete(ids=ids)

    def all_texts(self) -> list:
        res = self.collection.get()
        return res.get("documents", []) if res else []


def format_context(memories: list) -> str:
    """把检索到的记忆格式化成可注入 system prompt 的上下文文本。"""
    if not memories:
        return ""
    lines = ["【相关历史记忆】"]
    for m in memories:
        lines.append(f"- {m['text']}")
    return "\n".join(lines)
