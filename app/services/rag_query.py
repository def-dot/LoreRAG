"""RAG 检索服务 — 两阶段:多路召回 + RRF 融合 → Reranker 精排"""

from app.core.logging import get_logger
from app.schemas.rag import SearchResult
from app.services.embedding import encode
from app.services.rerank import rerank
from app.services.chunk import get_chunks_hybrid_rrf

logger = get_logger(__name__)

# 第一阶段:每路召回条数与 RRF 候选数(独立于最终 top_k)
RECALL_COUNT = 100
RRF_CANDIDATES = 50
RRF_K = 60


async def search(query: str, top_k: int = 5) -> list[SearchResult]:
    """
    两阶段混合检索:

    1. 多路召回 + RRF 融合 — 稠密向量(HNSW)与 tsvector BM25(GIN)双路召回,
       RRF 融合在单个 SQL 中完成,一次数据库往返;
    2. Reranker 精排 — 对候选用 cross-encoder (query, passage) 重打分,降序截取 top_k。
    """
    dense_vector = await encode(query)

    # ---------- 第一阶段: 多路召回 + RRF 融合（单 SQL）----------
    candidates = await get_chunks_hybrid_rrf(
        dense_vector, query,
        recall_count=RECALL_COUNT,
        rrf_candidates=RRF_CANDIDATES,
        rrf_k=RRF_K,
    )

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
