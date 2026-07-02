"""BGE-Reranker-v2-m3 精排服务 — 通过 TEI HTTP API"""

import httpx

TEI_RERANK_URL = "http://localhost:8082"
TEI_TIMEOUT = 120.0


async def rerank(query: str, passages: list[str]) -> list[float]:
    """对 (query, passage) 对用 cross-encoder 打分"""
    if not passages:
        return []

    async with httpx.AsyncClient(timeout=TEI_TIMEOUT) as client:
        response = await client.post(
            f"{TEI_RERANK_URL}/rerank",
            json={
                "query": query,
                "texts": [p[:1500] for p in passages],
                "truncate": True,
            },
        )
        response.raise_for_status()
        result = response.json()
        # TEI rerank 返回 [{"index": 0, "score": 0.98}, {"index": 1, "score": 0.45}]
        return [i["score"] for i in result]

