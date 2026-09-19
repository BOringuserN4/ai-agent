# -*- coding: utf-8 -*-
"""
agent/embedding_backends.py — 可插拔的 embedding 后端（云端 / 本地）

协议章延伸 · 本地推理，2026/09/19。

为什么做成「可插拔」而不是「直接换」：
  换 embedding 模型 = 换整个向量空间。旧向量和新向量**不可混用**，
  所以正确的做法不是删掉云端的代码，而是让两条路并存、可切换、可对比：
    - 用同一套语料 + 同一套用例，分别跑两个后端，比召回质量与延迟；
    - 质量没掉，才有理由切。

  ⇒ 这也让「回滚」变成改一个环境变量的事，而不是一次代码手术。

两个后端：
  - DashScopeBackend：阿里云 text-embedding-v3（现状，1024 维）
  - OllamaBackend   ：局域网 Ollama（Qwen3-Embedding-0.6B，1024 维）
    ⚠️ 维度必须对齐（都是 1024），否则 ChromaDB 的集合互不兼容。

关键约束（向量库）：
  不同后端必须用**不同的 collection / 目录**，否则会把两种向量混进一张表，
  检索结果直接崩坏且难排查。`collection_name` 已按后端自动区分。
"""
import os

import numpy as np


# 与 ChromaDB 集合共用：都是 1024 维，换后端不必改表结构
EMBED_DIM = 1024


class EmbeddingBackend:
    """embedding 后端接口。子类实现 `_embed_raw(texts) -> np.ndarray`。"""

    #: 后端标识，用于 collection 命名与日志
    name = "base"
    #: 输出维度（用于校验 / 建集合）
    dim = EMBED_DIM
    #: 是否支持 OpenAI 风格的 dimensions 参数（Matryoshka 截断）
    supports_dimensions = True

    def _embed_raw(self, texts: list) -> np.ndarray:
        raise NotImplementedError

    def embed(self, texts):
        """对外统一入口：返回**已归一化**的向量。

        归一化在基类做，保证两个后端的相似度口径一致（cosine）。
        支持 str（返回 (dim,)）与 list（返回 (N, dim)）。
        """
        single = isinstance(texts, str)
        batch = [texts] if single else list(texts)
        vecs = np.asarray(self._embed_raw(batch), dtype=np.float32)
        if vecs.ndim == 1:                      # 后端只回一条
            vecs = vecs.reshape(1, -1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs = vecs / np.maximum(norms, 1e-12)
        if vecs.shape[1] != self.dim:
            raise ValueError(
                f"{self.name} 输出 {vecs.shape[1]} 维，期望 {self.dim} 维。"
                f"维度不一致会让向量库混入两种空间，必须调齐。"
            )
        return vecs[0] if single else vecs

    def health(self) -> tuple:
        """自检：返回 (是否可用, 说明)。用于切换前先探活。"""
        try:
            self.embed("健康检查")
            return True, "ok"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"


class DashScopeBackend(EmbeddingBackend):
    """云端：阿里云 DashScope text-embedding-v3（OpenAI 兼容）。"""

    name = "dashscope"
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, model: str = "text-embedding-v3"):
        self.model = model
        self._client = None

    def _client_or_create(self):
        if self._client is None:
            from openai import OpenAI
            key = os.getenv("DASHSCOPE_API_KEY", "")
            if not key or len(key) < 10:
                raise RuntimeError("❌ 请在 .env 里配置 DASHSCOPE_API_KEY")
            self._client = OpenAI(api_key=key, base_url=self.BASE_URL)
        return self._client

    def _embed_raw(self, texts):
        resp = self._client_or_create().embeddings.create(
            model=self.model, input=texts, dimensions=self.dim,
        )
        return [x.embedding for x in resp.data]


class OllamaBackend(EmbeddingBackend):
    """本地：局域网 Ollama（OpenAI 兼容端点 /v1/embeddings）。

    用法：
        OllamaBackend(host="http://192.168.1.50:11434", model="qwen3-embedding:0.6b")

    设计取舍：
      - 走 OpenAI 兼容端点（而不是 Ollama 原生 /api/embed），
        因为记忆模块本来就用 OpenAI SDK，**换后端零改动**。
      - base_url 必须是「局域网 IP」而非 localhost：Ollama 默认只监听
        127.0.0.1，服务端必须设 OLLAMA_HOST=0.0.0.0:11434 才连得上（见部署说明）。
      - 不设 api_key：Ollama 不校验；但 OpenAI SDK 要求非空，故填占位符。
    """

    name = "ollama"
    # 多数 Ollama 版本对 dimensions 参数支持不一致，默认不带，避免 400
    supports_dimensions = False

    def __init__(self, host: str = None, model: str = None, timeout: float = 60.0):
        self.host = (host or os.getenv("OLLAMA_HOST_URL")
                     or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
        self.timeout = timeout
        self._client = None

    def _client_or_create(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key="ollama",              # 占位：Ollama 不校验
                base_url=f"{self.host}/v1",
                timeout=self.timeout,
            )
        return self._client

    def _embed_raw(self, texts):
        kwargs = {"model": self.model, "input": texts}
        if self.supports_dimensions:
            kwargs["dimensions"] = self.dim
        try:
            resp = self._client_or_create().embeddings.create(**kwargs)
        except Exception:
            # 兜底：某些版本不接受 dimensions，去掉重试一次
            kwargs.pop("dimensions", None)
            resp = self._client_or_create().embeddings.create(**kwargs)
        return [x.embedding for x in resp.data]


def get_backend(name: str = None, **kwargs) -> EmbeddingBackend:
    """按名字取后端。名字缺省时读环境变量 EMBEDDING_BACKEND（默认 dashscope）。

    这样「切回云端」= 改一个环境变量，不需要动代码。
    """
    name = (name or os.getenv("EMBEDDING_BACKEND") or "dashscope").lower()
    if name in ("dashscope", "cloud", "aliyun"):
        return DashScopeBackend(**kwargs)
    if name in ("ollama", "local"):
        return OllamaBackend(**kwargs)
    raise ValueError(f"未知 embedding 后端: {name}（可选 dashscope / ollama）")
