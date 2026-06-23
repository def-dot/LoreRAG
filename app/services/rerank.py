"""BGE-Reranker-v2-m3 精排服务 — 通过 TEI HTTP API"""

import httpx

TEI_RERANK_URL = "http://localhost:8082"
TEI_TIMEOUT = 120.0


async def rerank(query: str, passages: list[str]) -> list[float]:
    """对 (query, passage) 对用 cross-encoder 打分,返回 sigmoid 相关性分数 ∈ (0,1)"""
    if not passages:
        return []

    async with httpx.AsyncClient(timeout=TEI_TIMEOUT) as client:
        response = await client.post(
            f"{TEI_RERANK_URL}/rerank",
            json={
                "query": query,
                "texts": passages,
                "truncate": True,
            },
        )
        response.raise_for_status()
        result = response.json()
        # TEI rerank 返回 [{"index": 0, "score": 0.98}, {"index": 1, "score": 0.45}]
        # 需要按原顺序返回分数
        scores = [0.0] * len(passages)
        for item in result:
            scores[item["index"]] = item["score"]
        return scores
