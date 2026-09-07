# -*- coding: utf-8 -*-
"""
agent/memory.py — 长期记忆（LTM）模块（RAG 实现）

核心思路：
  - 记忆不塞进对话 history（否则上下文会爆炸），而是「外置存储 + 按需检索」。
  - 每条记忆 = 文本片段 + 语义向量 + 元数据。
  - 写入：对话产生的重要信息，向量化后存入本地 JSON。
  - 检索：用户提问时，用 embedding 语义搜索，取最相关的几条记忆注入上下文。

技术栈：
  - 阿里云 DashScope text-embedding-v3：远程 embedding API（OpenAI 兼容，中文友好，速度快）。
  - 纯 Python 向量检索（点积/余弦相似度），N=较小的记忆规模时足够，无需重型向量库。

价值：
  - 跨会话记住用户偏好、历史事实。
  - 不占上下文窗口：只取相关片段，而非全量携带。
"""
import os
import json
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
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "memory_store.json")


def _get_dashscope_key():
    """从环境变量读阿里云 DashScope key。"""
    return os.getenv("DASHSCOPE_API_KEY", "")


class MemoryStore:
    """一个简单的长期记忆仓库：JSON 持久化 + 语义检索。"""

    def __init__(self, model_name=DEFAULT_MODEL, top_k=4):
        self.top_k = top_k
        self.client = None  # 懒加载 OpenAI 兼容客户端（首次使用才建，省启动时间）
        self.model_name = model_name
        self.items = []   # 记忆条目：[{text, vector, meta}]
        self._load()

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

    # ---- 持久化 ----
    def _load(self):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                self.items = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.items = []

    def _save(self):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    # ---- 写入记忆 ----
    def add(self, text: str, meta: dict = None):
        """添加一条记忆：向量化 + 存储。使用文本哈希去重。"""
        text = text.strip()
        if not text:
            return
        # 去重：同文本不重复存
        digest = hashlib.md5(text.encode()).hexdigest()
        if any(it.get("digest") == digest for it in self.items):
            return
        # 向量化（单条，str）
        vec = self._embed(text)
        self.items.append({
            "text": text,
            "vector": vec.tolist(),
            "meta": meta or {},
            "digest": digest,
        })
        self._save()

    # ---- 检索记忆 ----
    def search(self, query: str, top_k: int = None):
        """
        语义检索：返回最相关的若干条记忆。
        Returns: list of {text, score, meta}
        """
        if not self.items:
            return []
        top_k = top_k or self.top_k
        q_vec = self._embed(query)  # str 单条
        # 对每条记忆算点积（余弦相似度，因为向量已归一化）
        best = []
        for it in self.items:
            score = float(np.dot(q_vec, np.asarray(it["vector"], dtype=np.float32)))
            best.append((score, it))
        best.sort(key=lambda x: x[0], reverse=True)
        result = []
        for score, it in best[:top_k]:
            result.append({
                "text": it["text"],
                "score": round(score, 4),
                "meta": it.get("meta", {}),
            })
        return result

    # ---- 工具方法 ----
    def count(self) -> int:
        return len(self.items)

    def clear(self):
        self.items = []
        self._save()

    def all_texts(self) -> list:
        return [it["text"] for it in self.items]


def format_context(memories: list) -> str:
    """把检索到的记忆格式化成可注入 system prompt 的上下文文本。"""
    if not memories:
        return ""
    lines = ["【相关历史记忆】"]
    for m in memories:
        lines.append(f"- {m['text']}")
    return "\n".join(lines)
