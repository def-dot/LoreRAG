"""RAG 检索服务 — 两阶段:多路召回 + RRF 融合 → Reranker 精排"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.schemas.rag import SearchResult, ChunkItem
from app.services.embedding import encode_hybrid
from app.services.rerank import rerank
from app.services.chunk import get_chunks_by_dense, get_chunks_by_parse

logger = get_logger(__name__)

# 第一阶段:每路召回条数与 RRF 候选数(独立于最终 top_k)
RECALL_COUNT = 100
RRF_CANDIDATES = 50
RRF_K = 60


async def search(query: str, top_k: int = 5) -> list[SearchResult]:
    """
    两阶段混合检索:

    1. 多路召回 + RRF 融合 — 稠密向量(HNSW)与稀疏词权重(GIN)各捞 RECALL_COUNT 条,
       RRF 合并取前 RRF_CANDIDATES 条候选;
    2. Reranker 精排 — 对候选用 cross-encoder (query, passage) 重打分,降序截取 top_k。
    """
    hybrid = await encode_hybrid(query)

    # ---------- 第一阶段: 多路召回 + RRF 融合 ----------
    dense_result = await get_chunks_by_dense(hybrid["dense"], limit=RECALL_COUNT)
    sparse_result = await get_chunks_by_parse(hybrid["sparse"], limit=RECALL_COUNT)

    # ---------- RRF 融合 ----------
    rrf_result: dict[int, SearchResult] = {}
    for rank, row in enumerate(dense_result):
        if row.chunk_id not in rrf_result:
            rrf_result[row.chunk_id] = row
        rrf_result[row.chunk_id].score += 1.0 / (RRF_K + rank + 1)

    for rank, row in enumerate(sparse_result):
        if row.chunk_id not in rrf_result:
            rrf_result[row.chunk_id] = row
        rrf_result[row.chunk_id].score += 1.0 / (RRF_K + rank + 1)

    candidates = sorted(rrf_result.values(), key=lambda x: x.score, reverse=True)[:RRF_CANDIDATES]
    if not candidates:
        return []

    # ---------- 第二阶段:Reranker 精排 ----------
    passages = [chunk.content or "" for chunk in candidates]
    rerank_scores = await rerank(query, passages)

    # 用 Reranker 分数覆盖 RRF 分数
    for candidate, score in zip(candidates, rerank_scores):
        candidate.score = score

    # 按 Reranker 分数降序,截 top_k
    return sorted(candidates, key=lambda x: x.score, reverse=True)[:top_k]
