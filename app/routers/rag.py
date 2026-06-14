"""RAG 知识库 API 路由"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.config import settings

from app.core.deps import SessionDep
from app.core.logging import get_logger
from app.models.document import DocumentStatus
from app.schemas.rag import (
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)
from app.services import rag as rag_service
from app.services.scheduler import cancel, schedule

logger = get_logger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG 知识库"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    db: SessionDep,
) -> Any:
    """
    上传 PDF 文档，加入解析队列异步处理

    处理流程：上传 → 入队 → Docling 全能力解析（OCR + 表格 + 公式 + 图片描述 + 图表提取） → 切片 → BGE-M3 向量化 → 入库
    """
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="仅支持 PDF 文件格式",
        )

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)  # type: ignore[arg-type]

    content = await file.read()

    doc = await rag_service.create_document(
        db,
        file_name=file.filename,  # type: ignore[arg-type]
        file_path=file_path,
        file_size=len(content),
        file_ext=file_ext,
    )

    with open(file_path, "wb") as f:
        f.write(content)

    # 丢入异步解析队列（限流 + 重试 + 启动恢复）
    schedule(doc.id)

    return UploadResponse(document_id=doc.id, file_name=file.filename, status=DocumentStatus.PENDING)  # type: ignore[arg-type]


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    req: SearchRequest,
    db: SessionDep,
) -> Any:
    """
    知识库检索

    使用稠密向量 + 全文检索 RRF 融合，返回最相关的文档切片。
    """
    results = await rag_service.search(req.query, db, req.top_k)
    return SearchResponse(results=results, total=len(results))


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(db: SessionDep) -> Any:
    """列出所有文档及其处理状态"""
    docs = await rag_service.list_documents(db)
    return DocumentListResponse(items=docs, total=len(docs))


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
    db: SessionDep,
) -> Any:
    """获取单个文档详情"""
    doc = await rag_service.get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return doc


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: int,
    db: SessionDep,
) -> Any:
    """删除指定文档及其所有切片"""
    deleted_chunks, file_name = await rag_service.delete_document_by_id(db, document_id)
    if deleted_chunks == 0 and not file_name:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return DeleteResponse(deleted_chunks=deleted_chunks, file_name=file_name)


@router.get("/queue/status")
async def get_queue_status() -> dict[str, Any]:
    """查看解析队列状态"""
    from app.services.scheduler import status
    return status()


@router.post("/queue/cancel/{document_id}")
async def cancel_parse(
    document_id: int,
    db: SessionDep,
) -> dict[str, Any]:
    """取消正在排队或解析中的文档"""
    ok = cancel(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"文档不在解析队列中: {document_id}")
    return {"document_id": document_id, "cancelled": True}
