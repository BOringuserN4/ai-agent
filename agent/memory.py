# -*- coding: utf-8 -*-
"""
agent/memory.py — 长期记忆（LTM）模块（RAG 实现，ChromaDB 版本）

核心思路：
  - 记忆不塞进对话 history（否则上下文会爆炸），而是「外置存储 + 按需检索」。
  - 每条记忆 = 文本片段 + 语义向量 + 元数据。
  - 写入：对话产生的重要信息，通过远程 embedding 生成向量后存入 ChromaDB。
  - 检索：用户提问时，用远程 embedding 生成查询向量，交给 ChromaDB 做近似最近邻（HNSW）检索，取 top-k 注入上下文。

技术栈：
  - embedding 后端**可插拔**（2026/09/19）：云端 DashScope text-embedding-v3 或
    局域网 Ollama（Qwen3-Embedding-0.6B），见 agent/embedding_backends.py。
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
import numpy as np
from dotenv import load_dotenv
from agent.embedding_backends import get_backend, EMBED_DIM

load_dotenv()

# 阿里云 DashScope embedding 模型（OpenAI 兼容接口，中文效果好，速度快，无需本地模型）
DEFAULT_MODEL = "text-embedding-v3"
# DashScope OpenAI 兼容端点
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# 默认输出维度（支持 Matryoshka：可动态调小省存储，用默认 1024）
EMBED_DIM = 1024

# ChromaDB 持久化目录（运行时生成，含用户信息，不入库）
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_data")
COLLECTION_NAME = "memory_store"


def _get_dashscope_key():
    """从环境变量读阿里云 DashScope key。"""
    return os.getenv("DASHSCOPE_API_KEY", "")


class MemoryStore:
    """基于 ChromaDB 的长期记忆仓库：持久化 + HNSW 语义检索。"""

    def __init__(self, model_name=DEFAULT_MODEL, top_k=8, backend=None,
                 chroma_dir=None):
        """
        Args:
            model_name: 兼容旧参数（保留，实际由 backend 决定模型）。
            top_k: 检索条数上限。
            backend: 可选的 embedding 后端实例（见 agent/embedding_backends.py）。
                     不传则按环境变量 EMBEDDING_BACKEND 取（默认云端 DashScope）。
            chroma_dir: 可选，覆盖向量库目录（评测用独立目录，不碰真实记忆）。
        """
        self.top_k = top_k
        self.model_name = model_name
        # 可插拔后端：默认仍是云端（不改变既有行为）
        self.backend = backend or get_backend()
        self.chroma_dir = chroma_dir or CHROMA_DIR
        # 不同后端的向量**不可混用** → collection 名按后端区分，避免混表。
        # 注意：后端可能带**自动回退**（本地挂了退云端），此时实际生效的后端
        # 会在运行时变化，所以 collection 不能只在构造时定死 ——
        # 每次读写前用 _sync_collection() 校正。
        self._ensure_chroma()
        self._sync_collection(initial=True)

    def _collection_name_for(self, backend_name: str) -> str:
        """按后端名推导 collection 名（云端沿用原名，保证既有数据不受影响）。"""
        return COLLECTION_NAME if backend_name == "dashscope" \
            else f"{COLLECTION_NAME}_{backend_name}"

    def _sync_collection(self, initial: bool = False):
        """让 collection 与**当前实际生效**的后端保持一致。

        回退还意味着「换了一个向量空间」，所以必须同时换表。
        这一步若漏掉，两种向量会混进同一张表，检索结果静默崩坏。
        """
        want = self._collection_name_for(self.backend.name)
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

    def _collection(self):
        return self.collection

    # ---- embedding（委托给可插拔后端，归一化在后端内统一做）----
    def _embed(self, texts):
        """把文本转成向量。后端可插拔（云端 DashScope / 本地 Ollama）。

        支持：
          - texts 是 str  → 返回单个向量 np.ndarray (dim,)
          - texts 是 list → 返回 (N, dim) 矩阵
        """
        return self.backend.embed(texts)

    # ---- 写入记忆 ----
    def add(self, text: str, meta: dict = None):
        """添加一条记忆：向量化 + 存储。使用文本哈希去重。"""
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
        # 向量化（单条，str）
        vec = self._embed(text)
        self.collection.add(
            ids=[digest],
            documents=[text],
            embeddings=[vec.tolist()],
            metadatas=[meta or {"type": "manual"}],
        )

    # ---- 检索记忆 ----
    def search(self, query: str, top_k: int = None, min_score: float = 0.6):
        """
        语义检索：返回最相关的若干条记忆。
        Returns: list of {text, score, meta}
        """
        self._sync_collection()          # 后端可能已回退 → 先对齐集合
        if self.collection.count() == 0:
            return []
        top_k = top_k or self.top_k
        q_vec = self._embed(query)  # str 单条
        # ChromaDB query：返回最近的 top_k 条，带 distance。
        res = self.collection.query(
            query_embeddings=[q_vec.tolist()],
            n_results=top_k,
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
