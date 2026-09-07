# -*- coding: utf-8 -*-
"""
agent/memory.py — 长期记忆（LTM）模块（RAG 实现）

核心思路：
  - 记忆不塞进对话 history（否则上下文会爆炸），而是「外置存储 + 按需检索」。
  - 每条记忆 = 文本片段 + 语义向量 + 元数据。
  - 写入：对话产生的重要信息，向量化后存入本地 JSON。
  - 检索：用户提问时，用 embedding 语义搜索，取最相关的几条记忆注入上下文。

技术栈：
  - sentence-transformers：本地 embedding（中文友好，离线可用）。
  - 纯 Python 向量检索（点积/余弦相似度），N=较小的记忆规模时足够，无需重型向量库。

价值：
  - 跨会话记住用户偏好、历史事实。
  - 不占上下文窗口：只取相关片段，而非全量携带。
"""
import os
import json
import hashlib
import numpy as np

# 本地 embedding 模型（中文友好，bge-small-zh 体积小、效果好）。首次运行会下载。
DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "memory_store.json")


class MemoryStore:
    """一个简单的长期记忆仓库：JSON 持久化 + 语义检索。"""

    def __init__(self, model_name=DEFAULT_MODEL, top_k=4):
        self.top_k = top_k
        self.model = None  # 懒加载 embedding 模型（首次使用才加载，省启动时间）
        self.model_name = model_name
        self.items = []   # 记忆条目：[{text, vector, meta}]
        self._load()

    # ---- embedding 模型（懒加载）----
    def _ensure_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def _embed(self, texts):
        """把文本列表转成向量（归一化，方便点积算相似度）。"""
        m = self._ensure_model()
        vecs = m.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)

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
        # 向量化（单条）
        vec = self._embed([text])[0]
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
        q_vec = self._embed([query])[0]
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
