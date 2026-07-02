"""RAG 检索服务 — 三种模式: BM25 / 向量 / 混合 + Reranker 精排"""

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.schemas.rag import SearchResult
from app.services.embedding import encode
from app.services.rerank import rerank
from app.services.chunk import get_chunks_bm25, get_chunks_vector, get_chunks_hybrid_rrf

logger = get_logger(__name__)

RECALL_COUNT = 100
RRF_CANDIDATES = 50
RRF_K = 60


async def search(query: str, top_k: int = 5, mode: str = "hybrid") -> tuple[list[SearchResult], list[str]]:
    """
    知识库检索，返回 (结果列表, 查询分词 tokens)。
    """
    tokens: list[str] = []

    # ---- 第一阶段: 召回 ----
    if mode == "bm25":
        candidates = await get_chunks_bm25(query, limit=top_k)
        tokens = await _tokenize_query(query)
    elif mode == "vector":
        dense_vector = await encode(query)
        candidates = await get_chunks_vector(dense_vector, limit=RECALL_COUNT)
    else:
        dense_vector = await encode(query)
        candidates = await get_chunks_hybrid_rrf(
            dense_vector, query,
            recall_count=RECALL_COUNT,
            rrf_candidates=RRF_CANDIDATES,
            rrf_k=RRF_K,
        )

    if not candidates:
        return [], tokens

    # ---- 第二阶段: Reranker 精排（BM25 跳过） ----
    if mode != "bm25":
        passages = [chunk.content or "" for chunk in candidates]
        rerank_scores = await rerank(query, passages)
        for candidate, score in zip(candidates, rerank_scores):
            candidate.score = score

    return sorted(candidates, key=lambda x: x.score, reverse=True)[:top_k], tokens


async def _tokenize_query(query: str) -> list[str]:
    """zhparser 分词，返回去重词列表（过滤单字虚词）"""
    token_sql = text("SELECT tsvector_to_array(to_tsvector('chinese', :query))")
    async with AsyncSessionLocal() as db:
        row = (await db.execute(token_sql, {"query": query})).fetchone()
        return list(row[0]) if row and row[0] else []
