"""文档管理 API 路由"""
import os
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.logging import get_logger
from app.schemas.rag import (
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    UploadResponse
)
from app.models.document import DocumentStatus
from app.services import document
from app.core.config import settings
from app.services.task import schedule

logger = get_logger(__name__)
router = APIRouter(prefix="/document", tags=["文档管理"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
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

    doc = await document.create_document(
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


@router.get("/", response_model=DocumentListResponse)
async def list_documents() -> Any:
    """列出所有文档及其处理状态"""
    docs = await document.list_documents()
    return DocumentListResponse(items=docs, total=len(docs))


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
) -> Any:
    """获取单个文档详情"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return doc


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: int,
) -> Any:
    """删除指定文档及其所有切片"""
    deleted_chunks, file_name = await document.delete_document_by_id(document_id)
    if deleted_chunks == 0 and not file_name:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return DeleteResponse(deleted_chunks=deleted_chunks, file_name=file_name)
