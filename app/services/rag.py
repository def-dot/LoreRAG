"""RAG 存储与检索服务 — pgvector 稠密检索 + JSONB 稀疏检索"""

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.rag import DocumentDetail, DocumentListItem, SearchResult
from app.services.document import process_document
from app.services.embedding import encode_hybrid, encode_hybrid_batch

logger = get_logger(__name__)


def _vector_to_str(vec: list[float]) -> str:
    """将向量列表转换为 PostgreSQL vector 字面量字符串"""
    return "[" + ",".join(str(v) for v in vec) + "]"


async def create_document(
    db: AsyncSession,
    file_name: str,
    file_path: str | None = None,
    file_size: int | None = None,
    file_ext: str | None = None,
) -> Document:
    now = datetime.now()
    doc = Document(
        file_name=file_name,
        file_path=file_path,
        file_size=file_size,
        file_ext=file_ext,
        status=DocumentStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def update_document_status(
    document_id: int,
    status: str,
    chunk_count: int = 0,
    error_message: str | None = None,
) -> Document:
    """更新文档处理状态"""
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            logger.warning("Document %d not found, skip status update", document_id)
            return

        doc.status = status
        doc.updated_at = datetime.now()

        if status == DocumentStatus.COMPLETED:
            doc.chunk_count = chunk_count
        if error_message is not None:
            doc.error_message = error_message

        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        logger.info("Document %d status updated to %s", document_id, status)
        return doc


async def process_and_store(document_id: int) -> None:
    """后台任务：更新状态 → 解析文档 → 切片 → 计算向量 → 入库 → 更新状态"""
    try:
        doc = await update_document_status(document_id, DocumentStatus.PROCESSING)

        chunks = await asyncio.to_thread(process_document, doc.file_path)
        if not chunks:
            logger.warning("No chunks produced from %s (document_id=%d)", doc.file_path, document_id)
            await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=0)
            return

        count = await store_chunks(chunks, document_id=document_id)
        await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=count)
        logger.info("Document processed successfully: %s (%d chunks)", doc.file_path, count)
    except Exception as exc:
        logger.exception("Failed to process document (document_id=%d)", document_id)
        await update_document_status(document_id, DocumentStatus.FAILED, error_message=str(exc)[:2000])


async def store_chunks(chunks: list[dict[str, Any]], document_id: int | None = None) -> int:
    """
    将切片批量写入数据库（含稠密向量 + 稀疏词权重计算）

    返回写入的切片数量
    """
    texts = [c["enriched_text"] for c in chunks]
    hybrid_outputs = encode_hybrid_batch(texts)

    async with AsyncSessionLocal() as db:
        for chunk_data, hybrid in zip(chunks, hybrid_outputs, strict=True):
            meta = chunk_data["metadata"]
            raw = chunk_data["raw_text"]
            enriched = chunk_data["enriched_text"]

            stmt = text("""
                INSERT INTO document_chunks
                    (document_id, file_name, page_numbers, heading_context, raw_content, enriched_content,
                     dense_vector, sparse_lexicon)
                VALUES
                    (:document_id, :file_name, CAST(:page_numbers AS INTEGER[]), :heading_context, :raw_content, :enriched_content,
                     CAST(:dense_vector AS vector), CAST(:sparse_lexicon AS jsonb))
            """)
            await db.execute(
                stmt,
                {
                    "document_id": document_id,
                    "file_name": meta["source_file"],
                    "page_numbers": meta["page_numbers"],
                    "heading_context": meta["heading_context"],
                    "raw_content": raw,
                    "enriched_content": enriched,
                    "dense_vector": _vector_to_str(hybrid["dense"]),
                    "sparse_lexicon": json.dumps(hybrid["sparse"], ensure_ascii=False),
                },
            )

        await db.commit()
    logger.info("Stored %d chunks for %s (document_id=%s)", len(chunks), chunks[0]["metadata"]["source_file"], document_id)
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
        await db.execute(
            sparse_sql,
            {
                "q_weights": json.dumps(hybrid["sparse"]),
                "tokens": tokens,
                "limit": top_k * 2,
            },
        )
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
    """列出所有文档及其处理状态"""
    stmt = select(Document).order_by(Document.created_at.desc())  # type: ignore[union-attr]
    rows = (await db.execute(stmt)).scalars().all()

    return [
        DocumentListItem(
            id=doc.id,  # type: ignore[arg-type]
            file_name=doc.file_name,
            file_path=doc.file_path,
            file_size=doc.file_size,
            file_ext=doc.file_ext,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in rows
    ]


async def get_document(db: AsyncSession, document_id: int) -> DocumentDetail | None:
    """获取单个文档详情"""
    doc = await db.get(Document, document_id)
    if doc is None:
        return None

    return DocumentDetail(
        id=doc.id,  # type: ignore[arg-type]
        file_name=doc.file_name,
        file_path=doc.file_path,
        file_size=doc.file_size,
        file_ext=doc.file_ext,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def delete_document_by_id(db: AsyncSession, document_id: int) -> tuple[int, str]:
    """
    删除文档及其关联切片，同时清理磁盘源文件

    返回 (删除切片数量, 文件名)
    """
    import os

    doc = await db.get(Document, document_id)
    if doc is None:
        return 0, ""

    file_name = doc.file_name
    file_path = doc.file_path

    # 删除关联切片
    chunk_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)  # type: ignore[arg-type]
    chunk_result = await db.execute(chunk_stmt)
    deleted_chunks = chunk_result.rowcount  # type: ignore[attr-defined]

    # 删除文档记录
    await db.delete(doc)
    await db.commit()

    # 清理磁盘源文件
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    logger.info("Deleted document %d (%s), %d chunks removed", document_id, file_name, deleted_chunks)
    return deleted_chunks, file_name
