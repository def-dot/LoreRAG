import os
from datetime import datetime

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.rag import DocumentDetail, DocumentListItem

logger = get_logger(__name__)


async def document_exists(file_name: str) -> bool:
    """检查同名文件是否已存在（排除已失败的记录）"""
    async with AsyncSessionLocal() as db:
        stmt = select(Document).where(
            Document.file_name == file_name
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


async def create_document(
    file_name: str,
    file_path: str | None = None,
    file_size: int | None = None,
    file_ext: str | None = None,
) -> Document:
    now = datetime.now()
    async with AsyncSessionLocal() as db:
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
    retry_count: int = 0,
) -> Document:
    """更新文档处理状态"""
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            logger.warning("Document %d not found, skip status update", document_id)
            return

        doc.status = status
        doc.updated_at = datetime.now()

        if status == DocumentStatus.PROCESSING:
            doc.parse_started_at = datetime.now()
        if status == DocumentStatus.COMPLETED:
            doc.chunk_count = chunk_count
            doc.parse_completed_at = datetime.now()
        if error_message is not None:
            doc.error_message = error_message
        if retry_count:
            doc.retry_count = retry_count

        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        logger.info("Document %d status updated to %s", document_id, status)
        return doc


async def list_documents() -> list[DocumentListItem]:
    """列出所有文档及其处理状态"""
    async with AsyncSessionLocal() as db:
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
                retry_count=doc.retry_count,
                error_message=doc.error_message,
                created_at=doc.created_at,
                parse_started_at=doc.parse_started_at,
                parse_completed_at=doc.parse_completed_at,
                updated_at=doc.updated_at,
            )
            for doc in rows
        ]


async def get_document(document_id: int) -> DocumentDetail | None:
    """获取单个文档详情"""
    async with AsyncSessionLocal() as db:
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
            retry_count=doc.retry_count,
            created_at=doc.created_at,
            parse_started_at=doc.parse_started_at,
            parse_completed_at=doc.parse_completed_at,
            updated_at=doc.updated_at,
        )


async def delete_document_by_id(document_id: int) -> tuple[int, str]:
    """
    删除文档及其关联切片，同时清理磁盘源文件

    返回 (删除切片数量, 文件名)
    """
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            return 0, ""

        if doc.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
            raise ValueError("文档正在处理中，请先取消后再删除")

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
