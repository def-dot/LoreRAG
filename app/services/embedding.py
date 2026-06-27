"""BGE-M3 向量嵌入服务 — 通过 TEI HTTP API"""

from __future__ import annotations

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
