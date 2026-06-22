"""切片向量化与批量入库"""

import asyncio
import json
from typing import Any

from sqlalchemy import text, select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.embedding import encode_hybrid_batch
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
    将切片批量写入数据库（含稠密向量 + 稀疏词权重）

    返回写入的切片数量
    """
    if not chunks:
        logger.warning("No chunks to insert for document_id=%d", document_id)
        return 0

    texts = [c["enriched_text"] for c in chunks]
    hybrid_outputs = await asyncio.to_thread(encode_hybrid_batch, texts)

    async with AsyncSessionLocal() as db:
        inserted_count = 0
        for chunk_data, hybrid in zip(chunks, hybrid_outputs, strict=True):
            try:
                meta = chunk_data["metadata"]
                await db.execute(
                    text(
                        """
                        INSERT INTO document_chunks
                            (document_id, file_name, page_numbers, heading_context,
                             raw_content, enriched_content, dense_vector, sparse_lexicon)
                        VALUES
                            (:document_id, :file_name, CAST(:page_numbers AS INTEGER[]),
                             :heading_context, :raw_content, :enriched_content,
                             CAST(:dense_vector AS vector), CAST(:sparse_lexicon AS jsonb))
                        """
                    ),
                    {
                        "document_id": document_id,
                        "file_name": meta["source_file"],
                        "page_numbers": meta["page_numbers"],
                        "heading_context": meta["heading_context"],
                        "raw_content": chunk_data["raw_text"],
                        "enriched_content": chunk_data["enriched_text"],
                        "dense_vector": _vector_to_str(hybrid["dense"]),
                        "sparse_lexicon": json.dumps(hybrid["sparse"], ensure_ascii=False),
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


async def get_chunks_by_dense(query_vec: list[float], limit: int=100) -> list[SearchResult]:
    query_vec_str = _vector_to_str(query_vec)
    dense_sql = text("""
            SELECT id, document_id, file_name, page_numbers, heading_context, raw_content, 
                     dense_vector <=> CAST(:qvec AS vector) as score
            FROM document_chunks
            ORDER BY dense_vector <=> CAST(:qvec AS vector)
            LIMIT :limit
        """)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(dense_sql, {"qvec": query_vec_str, "limit": limit})).fetchall()
        return [
            SearchResult(
                chunk_id=chunk[0],
                document_id=chunk[1],
                file_name=chunk[2],
                page_numbers=chunk[3],
                heading_context=chunk[4],
                content=chunk[5],
                score=chunk[6],
            )
            for chunk in rows
        ]


async def get_chunks_by_parse(query_parse: dict[str, float], limit: int=100) -> list[SearchResult]:
    tokens = list(query_parse.keys())
    sparse_sql = text("""
            SELECT id, document_id, file_name, page_numbers, heading_context, raw_content,
                (SELECT SUM(COALESCE(
                    (sparse_lexicon->>t.key)::float * (t.value)::float, 0
                ))
                FROM jsonb_each_text(CAST(:q_weights AS jsonb)) AS t(key, value)) AS score
            FROM document_chunks
            WHERE sparse_lexicon ?| :tokens
            ORDER BY score DESC
            LIMIT :limit
        """)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                sparse_sql,
                {
                    "q_weights": json.dumps(query_parse),
                    "tokens": tokens,
                    "limit": limit,
                },
            )
        ).fetchall()
        return [
            SearchResult(
                chunk_id=chunk[0],
                document_id=chunk[1],
                file_name=chunk[2],
                page_numbers=chunk[3],
                heading_context=chunk[4],
                content=chunk[5],
                score=chunk[6],
            )
            for chunk in rows
        ]

