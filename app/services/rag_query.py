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

    """
    WITH dense_search AS (
        -- 第一路：稠密向量检索，按余弦距离排序，计算出它的排名 (dense_rank)
        SELECT id, ROW_NUMBER() OVER (ORDER BY dense_embedding <=> %s) as dense_rank
        FROM doc_chunks
        ORDER BY dense_embedding <=> %s
        LIMIT 40 -- 粗筛前 40 个
    ),
    sparse_search AS (
        -- 第二路：稀疏文本检索（BM25变体），利用 ts_rank_cd 计算字面匹配度排名 (sparse_rank)
        SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv_content, to_tsquery('chinese', %s)) DESC) as sparse_rank
        FROM doc_chunks
        WHERE tsv_content @@ to_tsquery('chinese', %s)
        ORDER BY ts_rank_cd(tsv_content, to_tsquery('chinese', %s)) DESC
        LIMIT 40 -- 粗筛前 40 个
    )
    -- 第三步：利用 RRF 公式将两路粗筛结果合并，并重新计算总分
    SELECT 
        coalesce(d.id, s.id) as id,
        c.content,
        -- RRF 融合公式，常数固定为 60（业界标准）
        (coalesce(1.0 / (60.0 + d.dense_rank), 0.0) + coalesce(1.0 / (60.0 + s.sparse_rank), 0.0)) as rrf_score
    FROM dense_search d
    FULL OUTER JOIN sparse_search s ON d.id = s.id
    JOIN doc_chunks c ON c.id = coalesce(d.id, s.id)
    ORDER BY rrf_score DESC
    LIMIT 5; -- 最终精准挑出前 5 个喂给大模型
    """

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
