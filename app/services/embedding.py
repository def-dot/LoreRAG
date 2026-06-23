"""BGE-M3 向量嵌入服务 — 通过 TEI HTTP API"""

from __future__ import annotations

from typing import Any

import httpx

TEI_EMBED_URL = "http://localhost:8081"
TEI_TIMEOUT = 120.0


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 TEI embedding 接口,返回稠密向量列表"""
    async with httpx.AsyncClient(timeout=TEI_TIMEOUT) as client:
        response = await client.post(
            f"{TEI_EMBED_URL}/embed",
            json={"inputs": texts, "truncate": True},
        )
        response.raise_for_status()
        result = response.json()
        # /embed 返回: 单条 → [[float, ...]]  多条 → [[float, ...], [float, ...]]
        if isinstance(result[0], (int, float)):
            return [result]
        return result


async def encode(text: str) -> list[float]:
    """单条文本编码为稠密向量"""
    results = await _embed_texts([text])
    return results[0]


async def encode_batch(texts: list[str]) -> list[list[float]]:
    """批量文本编码为稠密向量"""
    return await _embed_texts(texts)


async def encode_hybrid(text: str) -> dict[str, Any]:
    """单条文本编码为稠密向量 + 稀疏词权重"""
    dense = await encode(text)
    # TEI 默认仅返回稠密向量;稀疏词权重需要通过 TEI 的 sparse 参数启用
    # 若不可用则返回空字典,稀疏检索路径将返回 0 条结果
    return {"dense": dense, "sparse": {}}


async def encode_hybrid_batch(texts: list[str]) -> list[dict[str, Any]]:
    """批量文本编码为稠密向量 + 稀疏词权重"""
    denses = await encode_batch(texts)
    return [{"dense": d, "sparse": {}} for d in denses]
