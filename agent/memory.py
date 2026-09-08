# -*- coding: utf-8 -*-
"""
agent/memory.py — 长期记忆（LTM）模块（RAG 实现，ChromaDB 版本）

核心思路：
  - 记忆不塞进对话 history（否则上下文会爆炸），而是「外置存储 + 按需检索」。
  - 每条记忆 = 文本片段 + 语义向量 + 元数据。
  - 写入：对话产生的重要信息，通过远程 embedding 生成向量后存入 ChromaDB。
  - 检索：用户提问时，用远程 embedding 生成查询向量，交给 ChromaDB 做近似最近邻（HNSW）检索，取 top-k 注入上下文。

技术栈：
  - 阿里云 DashScope text-embedding-v3：远程 embedding API（OpenAI 兼容，中文友好，速度快）。
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

    def __init__(self, model_name=DEFAULT_MODEL, top_k=4):
        self.top_k = top_k
        self.model_name = model_name
        self.client = None  # 懒加载 OpenAI 兼容客户端（首次使用才建，省启动时间）
        self._ensure_chroma()
        self.collection = self._collection()

    # ---- ChromaDB 持久化 ----
    def _ensure_chroma(self):
        """初始化 ChromaDB 客户端 + 集合（首次使用时创建）。"""
        import chromadb
        # PersistentClient：数据写到磁盘，跨进程重启后还在。
        self._chroma = chromadb.PersistentClient(path=CHROMA_DIR)
        # 用 cosine 距离（等价于余弦相似度，向量已归一化）。
        # get_or_create_collection 已存在则复用，避免重建丢数据。
        self.collection = self._chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _collection(self):
        return self.collection

    # ---- embedding 客户端（懒加载）----
    def _ensure_client(self):
        """懒加载 OpenAI 兼容客户端（首次使用才建）。"""
        if self.client is None:
            from openai import OpenAI
            key = _get_dashscope_key()
            if not key or len(key) < 10:
                raise RuntimeError("❌ 请在 .env 里配置 DASHSCOPE_API_KEY")
            self.client = OpenAI(api_key=key, base_url=DASHSCOPE_BASE_URL)
        return self.client

    def _embed(self, texts):
        """把文本转成向量（远程 API，归一化方便点积算相似度）。

        支持：
          - texts 是 str  → 返回单个向量 np.ndarray (dim,)
          - texts 是 list → 返回 (N, dim) 矩阵
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        client = self._ensure_client()
        resp = client.embeddings.create(
            model=self.model_name,
            input=texts,
            dimensions=EMBED_DIM,
        )
        # DashScope/text-embedding-v3 输出已归一化，这里保险起见再归一化一次
        vecs = np.asarray([x.embedding for x in resp.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs = vecs / np.maximum(norms, 1e-12)  # 归一化，避免除零
        if single:
            return vecs[0]
        return vecs

    # ---- 写入记忆 ----
    def add(self, text: str, meta: dict = None):
        """添加一条记忆：向量化 + 存储。使用文本哈希去重。"""
        text = text.strip()
        if not text:
            return
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
    def search(self, query: str, top_k: int = None):
        """
        语义检索：返回最相关的若干条记忆。
        Returns: list of {text, score, meta}
        """
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
        # ChromaDB 1.5+ 不接受空 where={}，直接取所有 id 批量删除
        all_ids = self.collection.get().get("ids", [])
        if all_ids:
            self.collection.delete(ids=all_ids)

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
