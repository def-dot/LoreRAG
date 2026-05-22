"""BGE-M3 向量嵌入服务 — 单例懒加载，支持稠密 + 稀疏双路输出"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_model() -> Any:
    """延迟导入 FlagEmbedding，先确保模型已缓存到本地"""
    from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]
    return BGEM3FlagModel(
        "./models/bge-m3",
        use_fp16=True
    )


def encode(text: str) -> list[float]:
    """单条文本编码为稠密向量"""
    model = _get_model()
    return model.encode([text], return_dense=True, return_sparse=True)["dense"][0].tolist()


def encode_batch(texts: list[str]) -> list[list[float]]:
    """批量文本编码为稠密向量"""
    model = _get_model()
    output = model.encode(texts, return_dense=True)
    return [vec.tolist() for vec in output["dense"]]


def encode_hybrid(text: str) -> dict[str, Any]:
    """单条文本编码为稠密向量 + 稀疏词权重"""
    model = _get_model()
    output = model.encode([text], return_dense=True, return_sparse=True)
    sparse = output["lexical_weights"][0]
    return {
        "dense": output["dense"][0].tolist(),
        "sparse": {k: float(v) for k, v in sparse.items()},
    }


def encode_hybrid_batch(texts: list[str]) -> list[dict[str, Any]]:
    """批量文本编码为稠密向量 + 稀疏词权重"""
    model = _get_model()
    output = model.encode(texts, return_dense=True, return_sparse=True)
    results = []
    for dense_vec, lexical in zip(output["dense"], output["lexical_weights"]):
        results.append({
            "dense": dense_vec.tolist(),
            "sparse": {k: float(v) for k, v in lexical.items()},
        })
    return results
