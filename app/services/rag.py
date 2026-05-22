"""RAG 存储与检索服务 — pgvector 稠密检索 + JSONB 稀疏检索"""

import json
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.document import DocumentChunk
from app.schemas.rag import DocumentListItem, SearchResult
from app.services.embedding import encode_hybrid, encode_hybrid_batch

logger = get_logger(__name__)


def _vector_to_str(vec: list[float]) -> str:
    """将向量列表转换为 PostgreSQL vector 字面量字符串"""
    return "[" + ",".join(str(v) for v in vec) + "]"


async def store_chunks(chunks: list[dict[str, Any]], db: AsyncSession) -> int:
    """
    将切片批量写入数据库（含稠密向量 + 稀疏词权重计算）

    返回写入的切片数量
    """
    texts = [c["enriched_text"] for c in chunks]
    hybrid_outputs = encode_hybrid_batch(texts)

    for chunk_data, hybrid in zip(chunks, hybrid_outputs, strict=True):
        meta = chunk_data["metadata"]
        raw = chunk_data["raw_text"]
        enriched = chunk_data["enriched_text"]

        stmt = text("""
            INSERT INTO document_chunks
                (file_name, page_numbers, heading_context, raw_content, enriched_content,
                 dense_vector, c_lexicon)
            VALUES
                (:file_name, :page_numbers, :heading_context, :raw_content, :enriched_content,
                 CAST(:dense_vector AS vector), :sparse_lexicon::jsonb)
        """)
        await db.execute(
            stmt,
            {
                "file_name": meta["source_file"],
                "page_numbers": meta["page_numbers"],
                "heading_context": meta["heading_context"],
                "raw_content": raw,
                "enriched_content": enriched,
                "dense_vector": _vector_to_str(hybrid["dense"]),
                "sparse_lexicon": json.dumps(hybrid["sparse"]),
            },
        )

    await db.commit()
    logger.info("Stored %d chunks for %s", len(chunks), chunks[0]["metadata"]["source_file"])
    return len(chunks)


async def search(query: str, db: AsyncSession, top_k: int = 5) -> list[SearchResult]:
    """
    混合检索：稠密向量相似度 + JSONB 稀疏词权重 RRF 融合

    1. 稠密向量检索（HNSW 索引加速）
    2. 稀疏词权重检索（GIN 索引加速）
    3. RRF (Reciprocal Rank Fusion) 融合两路结果
    """
    hybrid = encode_hybrid(query)
    vec_str = _vector_to_str(hybrid["dense"])
    tokens = list(hybrid["sparse"].keys())

    # 稠密向量检索
    dense_sql = text("""
        SELECT id, file_name, page_numbers, heading_context, raw_content
        FROM document_chunks
        ORDER BY dense_vector <=> CAST(:qvec AS vector)
        LIMIT :limit
    """)
    dense_rows = (await db.execute(dense_sql, {"qvec": vec_str, "limit": top_k * 2})).fetchall()

    # 稀疏词权重检索
    sparse_sql = text("""
        SELECT id, file_name, page_numbers, heading_context, raw_content,
               (SELECT SUM(COALESCE(
                   (sparse_lexicon->>t.key)::float * (t.value)::float, 0
               ))
               FROM jsonb_each_text(:q_weights::jsonb) AS t(key, value)) AS sparse_score
        FROM document_chunks
        WHERE sparse_lexicon ?| :tokens
        ORDER BY sparse_score DESC
        LIMIT :limit
    """)
    sparse_rows = (
        await db.execute(sparse_sql, {
            "q_weights": json.dumps(hybrid["sparse"]),
            "tokens": tokens,
            "limit": top_k * 2,
        })
    ).fetchall()

    # RRF 融合
    k = 60
    scores: dict[int, float] = {}
    chunk_data: dict[int, dict[str, Any]] = {}

    def _add_row(row: Any, rank: int) -> None:
        scores[row[0]] = scores.get(row[0], 0) + 1.0 / (k + rank + 1)
        if row[0] not in chunk_data:
            chunk_data[row[0]] = {
                "file_name": row[1],
                "page_numbers": row[2] or [],
                "heading_context": row[3] or "",
                "content": row[4],
            }

    for rank, row in enumerate(dense_rows):
        _add_row(row, rank)

    for rank, row in enumerate(sparse_rows):
        _add_row(row, rank)

    # 按融合分数降序排列
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        SearchResult(
            chunk_id=cid,
            file_name=chunk_data[cid]["file_name"],
            page_numbers=chunk_data[cid]["page_numbers"],
            heading_context=chunk_data[cid]["heading_context"],
            content=chunk_data[cid]["content"],
            score=score,
        )
        for cid, score in ranked
    ]


async def list_documents(db: AsyncSession) -> list[DocumentListItem]:
    """列出所有已入库文档及其切片数量"""
    stmt = (
        select(
            DocumentChunk.file_name,  # type: ignore[call-overload]
            func.count(DocumentChunk.id).label("chunk_count"),  # type: ignore[arg-type]
        )
        .group_by(DocumentChunk.file_name)
        .order_by(DocumentChunk.file_name)
    )
    rows = (await db.execute(stmt)).fetchall()

    # 获取每个文档的页码范围
    results: list[DocumentListItem] = []
    for row in rows:
        file_name = row[0]
        page_stmt = select(func.unnest(DocumentChunk.page_numbers)).where(DocumentChunk.file_name == file_name)
        pages = sorted(set((await db.execute(page_stmt)).scalars().all()))
        results.append(DocumentListItem(file_name=file_name, chunk_count=row[1], page_numbers=pages))

    return results


async def delete_document(file_name: str, db: AsyncSession) -> int:
    """删除文档的所有切片，返回删除数量"""
    stmt = delete(DocumentChunk).where(DocumentChunk.file_name == file_name)  # type: ignore[arg-type]
    result = await db.execute(stmt)
    await db.commit()
    deleted = result.rowcount  # type: ignore[attr-defined]
    logger.info(f"Deleted {deleted} chunks for {file_name}")
    return deleted  # type: ignore[no-any-return]
