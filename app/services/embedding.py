"""BGE-M3 向量嵌入服务 — 单例懒加载，支持稠密 + 稀疏双路输出"""

from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _get_model() -> Any:
    """延迟导入 FlagEmbedding，先确保模型已缓存到本地"""
    from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]
    return BGEM3FlagModel(
        "./hub/bge-m3",
        use_fp16=True,
    )


@lru_cache(maxsize=1)
def _get_tokenizer() -> Any:
    """获取模型的 tokenizer，用于将 token ID 解码为文本"""
    model = _get_model()
    return model.tokenizer


def _decode_sparse_weights(lexical: dict) -> dict[str, float]:
    """将稀疏词权重中的 token ID key 解码为实际文本 token"""
    tokenizer = _get_tokenizer()
    decoded: dict[str, float] = {}
    for k, v in lexical.items():
        try:
            token_id = int(k)
            token_text = tokenizer.convert_ids_to_tokens(token_id)
            # 去除 SentencePiece 的 ▁ 前缀（表示词首空格）
            token_text = token_text.lstrip("▁")
        except (ValueError, TypeError):
            token_text = str(k)
        decoded[token_text] = float(v)
    return decoded


def encode(text: str) -> list[float]:
    """单条文本编码为稠密向量"""
    model = _get_model()
    return model.encode([text], return_dense=True)["dense"][0].tolist()


def encode_batch(texts: list[str]) -> list[list[float]]:
    """批量文本编码为稠密向量"""
    model = _get_model()
    output = model.encode(texts, return_dense=True)
    return [vec.tolist() for vec in output["dense"]]


def encode_hybrid(text: str) -> dict[str, Any]:
    """单条文本编码为稠密向量 + 稀疏词权重"""
    model = _get_model()
    output = model.encode([text], return_dense=True, return_sparse=True)
    return {
        "dense": output["dense"][0].tolist(),
        "sparse": _decode_sparse_weights(output["lexical_weights"][0]),
    }


def encode_hybrid_batch(texts: list[str]) -> list[dict[str, Any]]:
    """批量文本编码为稠密向量 + 稀疏词权重"""
    model = _get_model()
    output = model.encode(texts, return_dense=True, return_sparse=True)
    results = []
    for dense_vec, lexical in zip(output["dense_vecs"], output["lexical_weights"]):
        results.append({
            "dense": dense_vec.tolist(),
            "sparse": _decode_sparse_weights(lexical),
        })
    return results
