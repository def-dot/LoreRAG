"""切片向量化与批量入库"""

import json
from typing import Any

from sqlalchemy import text, select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.embedding import encode_hybrid_batch
from app.schemas.rag import ChunkItem
from app.models.document import Document, DocumentChunk

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
        return 0

    texts = [c["enriched_text"] for c in chunks]
    hybrid_outputs = encode_hybrid_batch(texts)

    async with AsyncSessionLocal() as db:
        for chunk_data, hybrid in zip(chunks, hybrid_outputs, strict=True):
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
        await db.commit()

    logger.info("Stored %d chunks (document_id=%d)", len(chunks), document_id)
    return len(chunks)
