"""文档管理 API 路由"""
import os
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.logging import get_logger
from app.core.response import UnifiedResponseRoute
from app.schemas.rag import (
    ChunkListResponse,
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    UploadResponse
)
from app.models.document import DocumentStatus
from app.services import document, chunk
from app.core.config import settings
from app.services.scheduler import cancel_and_await, schedule

logger = get_logger(__name__)
router = APIRouter(prefix="/document", tags=["文档管理"], route_class=UnifiedResponseRoute)


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
) -> Any:
    """
    上传 PDF 文档，加入解析队列异步处理

    处理流程：上传 → 入队 → Docling 全能力解析（OCR + 表格 + 公式 + 图片描述 + 图表提取） → 切片 → BGE-M3 向量化 → 入库
    """
    file_name = file.filename  # type: ignore[arg-type]
    file_ext = os.path.splitext(file_name or "")[1].lower()
    if file_ext != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="仅支持 PDF 文件格式",
        )

    if await document.document_exists(file_name):
        raise HTTPException(
            status_code=409,
            detail=f"文件已存在: {file_name}",
        )

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file_name)

    content = await file.read()

    # 文件大小检查
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="文件内容为空",
        )
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大：{file_size / 1024 / 1024:.2f}MB，最大支持 {settings.MAX_FILE_SIZE / 1024 / 1024:.0f}MB",
        )

    logger.info("Uploading file: %s (%.2f MB)", file_name, file_size / 1024 / 1024)

    with open(file_path, "wb") as f:
        f.write(content)

    doc = await document.create_document(
        file_name=file_name,
        file_path=file_path,
        file_size=len(content),
        file_ext=file_ext,
    )
    
    # 丢入异步解析队列（限流 + 重试 + 启动恢复）
    schedule(doc.id)

    return UploadResponse(document_id=doc.id, file_name=file_name, status=DocumentStatus.PENDING)  # type: ignore[arg-type]


@router.get("/", response_model=DocumentListResponse)
async def list_documents() -> Any:
    """列出所有文档及其处理状态"""
    docs = await document.list_documents()
    return DocumentListResponse(items=docs, total=len(docs))


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(document_id: int) -> Any:
    """列出文档的所有切片（不含向量数据）"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    chunks = await chunk.list_chunks(document_id)
    return ChunkListResponse(items=chunks, total=len(chunks))


@router.get("/{document_id}/download")
async def download_document(document_id: int) -> Any:
    """下载原始文件"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    path = doc.file_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在或已被清理")
    return FileResponse(
        path,
        filename=doc.file_name,
        media_type="application/octet-stream",
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: int,
) -> Any:
    """获取单个文档详情"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    return doc


@router.post("/{document_id}/cancel")
async def cancel_document(document_id: int) -> dict[str, Any]:
    """取消正在排队或解析中的文档"""
    ok = await cancel_and_await(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"文档不在解析队列中: {document_id}")
    return {"document_id": document_id, "cancelled": True}


@router.post("/{document_id}/retry")
async def retry_document(document_id: int) -> dict[str, Any]:
    """重试失败的文档"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    if doc.status != DocumentStatus.FAILED:
        raise HTTPException(status_code=400, detail="仅失败的文档可以重试")
    await document.update_document_status(document_id, DocumentStatus.PENDING)
    schedule(document_id)
    return {"document_id": document_id, "retried": True}


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: int,
) -> Any:
    """删除指定文档及其所有切片"""
    doc = await document.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")
    if doc.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        await cancel_and_await(document_id)
    deleted_chunks, file_name = await document.delete_document_by_id(document_id)
    return DeleteResponse(deleted_chunks=deleted_chunks, file_name=file_name)


@router.get("/{document_id}/pages")
async def get_document_pages(document_id: int) -> dict[str, Any]:
    """获取文档每页的解析结果"""
    pages = await document.get_document_pages(document_id)
    return {"pages": pages, "total": len(pages)}
