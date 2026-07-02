"""切片向量化与批量入库"""

import asyncio
from typing import Any

from sqlalchemy import text, select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.embedding import encode_batch
from app.schemas.rag import ChunkItem, SearchResult
from app.models.document import DocumentChunk

logger = get_logger(__name__)


def _vector_to_str(vec: list[float]) -> str:
    """将向量列表转换为 PostgreSQL vector 字面量"""
    return "[" + ",".join(str(v) for v in vec) + "]"


async def list_chunks(document_id: int) -> list[ChunkItem]:
    """列出文档的所有切片（不含向量数据）"""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.id)
        )
        rows = (await db.execute(stmt)).scalars().all()

        return [
            ChunkItem(
                id=chunk.id,
                document_id=chunk.document_id,
                file_name=chunk.file_name,
                page_numbers=chunk.page_numbers or [],
                heading_context=chunk.heading_context or "",
                raw_content=chunk.raw_content or "",
            )
            for chunk in rows
        ]


async def insert_chunks(chunks: list[dict[str, Any]], document_id: int) -> int:
    """
    将切片批量写入数据库（含稠密向量，tsv_content 由 PostgreSQL 触发器自动生成）

    返回写入的切片数量
    """
    if not chunks:
        logger.warning("No chunks to insert for document_id=%d", document_id)
        return 0

    texts = [c["enriched_text"] for c in chunks]
    dense_vectors = await encode_batch(texts)

    async with AsyncSessionLocal() as db:
        inserted_count = 0
        for chunk_data, dense_vec in zip(chunks, dense_vectors, strict=True):
            try:
                meta = chunk_data["metadata"]
                await db.execute(
                    text(
                        """
                        INSERT INTO document_chunks
                            (document_id, file_name, page_numbers, heading_context,
                             raw_content, enriched_content, dense_vector)
                        VALUES
                            (:document_id, :file_name, CAST(:page_numbers AS INTEGER[]),
                             :heading_context, :raw_content, :enriched_content,
                             CAST(:dense_vector AS vector))
                        """
                    ),
                    {
                        "document_id": document_id,
                        "file_name": meta["source_file"],
                        "page_numbers": meta["page_numbers"],
                        "heading_context": meta["heading_context"],
                        "raw_content": chunk_data["raw_text"],
                        "enriched_content": chunk_data["enriched_text"],
                        "dense_vector": _vector_to_str(dense_vec),
                    },
                )
                inserted_count += 1
            except Exception as e:
                logger.error("Failed to insert chunk %d for document %d: %s",
                            inserted_count + 1, document_id, e, exc_info=True)
                # 单个chunk失败不影响其他chunk，继续处理
                continue

        await db.commit()
        logger.info("Stored %d/%d chunks (document_id=%d)", inserted_count, len(chunks), document_id)
        return inserted_count


async def get_chunks_bm25(query_text: str, limit: int = 100) -> list[SearchResult]:
    """BM25 全文检索 — tsvector + zhparser + OR 语义"""
    bm25_sql = text("""
            WITH qt AS (
                SELECT to_tsquery('chinese', array_to_string(tsvector_to_array(to_tsvector('chinese', :query)), ' | ')) AS q
            )
            SELECT id, document_id, file_name, page_numbers, heading_context, raw_content,
                   ts_rank(tsv_content, qt.q) AS score
            FROM document_chunks, qt
            WHERE tsv_content @@ qt.q
            ORDER BY score DESC
            LIMIT :limit
        """)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(bm25_sql, {"query": query_text, "limit": limit})).fetchall()
        return [_row_to_result(r) for r in rows]


async def get_chunks_vector(query_vec: list[float], limit: int = 100) -> list[SearchResult]:
    """稠密向量检索 — HNSW 余弦相似度"""
    vector_sql = text("""
            WITH qv AS (
                SELECT CAST(:qvec AS vector) AS v
            )
            SELECT id, document_id, file_name, page_numbers, heading_context, raw_content,
                   1.0 - (dense_vector <=> qv.v) AS score
            FROM document_chunks, qv
            ORDER BY dense_vector <=> qv.v
            LIMIT :limit
        """)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(vector_sql, {"qvec": _vector_to_str(query_vec), "limit": limit})).fetchall()
        return [_row_to_result(r) for r in rows]


def _row_to_result(row) -> SearchResult:
    """将 DB 行转为 SearchResult"""
    return SearchResult(
        chunk_id=row[0],
        document_id=row[1],
        file_name=row[2],
        page_numbers=row[3],
        heading_context=row[4],
        content=row[5],
        score=row[6],
    )


async def get_chunks_hybrid_rrf(
    query_vec: list[float],
    query_text: str,
    recall_count: int = 100,
    rrf_candidates: int = 50,
    rrf_k: int = 60,
) -> list[SearchResult]:
    """单 SQL 完成 稠密向量 + tsvector BM25 双路召回 + RRF 融合，一次数据库往返"""
    query_vec_str = _vector_to_str(query_vec)
    hybrid_sql = text("""
            WITH qv AS (
                SELECT CAST(:qvec AS vector) AS v
            ),
            qt AS (
                SELECT to_tsquery('chinese', array_to_string(tsvector_to_array(to_tsvector('chinese', :query)), ' | ')) AS q
            ),
            dense_search AS (
                SELECT id, document_id, file_name, page_numbers, heading_context, raw_content,
                       ROW_NUMBER() OVER (ORDER BY dense_vector <=> qv.v) AS rank
                FROM document_chunks, qv
                ORDER BY dense_vector <=> qv.v
                LIMIT :recall_count
            ),
            sparse_search AS (
                SELECT id, document_id, file_name, page_numbers, heading_context, raw_content,
                       ROW_NUMBER() OVER (ORDER BY ts_rank(tsv_content, qt.q) DESC) AS rank
                FROM document_chunks, qt
                WHERE tsv_content @@ qt.q
                ORDER BY ts_rank(tsv_content, qt.q) DESC
                LIMIT :recall_count
            )
            SELECT
                COALESCE(d.id, s.id)              AS id,
                COALESCE(d.document_id, s.document_id) AS document_id,
                COALESCE(d.file_name, s.file_name) AS file_name,
                COALESCE(d.page_numbers, s.page_numbers) AS page_numbers,
                COALESCE(d.heading_context, s.heading_context) AS heading_context,
                COALESCE(d.raw_content, s.raw_content) AS raw_content,
                COALESCE(1.0 / (:rrf_k + d.rank), 0.0)
                    + COALESCE(1.0 / (:rrf_k + s.rank), 0.0) AS score
            FROM dense_search d
            FULL OUTER JOIN sparse_search s ON d.id = s.id
            ORDER BY score DESC
            LIMIT :rrf_candidates
        """)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                hybrid_sql,
                {
                    "qvec": query_vec_str,
                    "query": query_text,
                    "recall_count": recall_count,
                    "rrf_candidates": rrf_candidates,
                    "rrf_k": rrf_k,
                },
            )
        ).fetchall()
        return [_row_to_result(r) for r in rows]
