"""RAG 知识库 API 路由"""

import os
from typing import Any

from docling.datamodel.base_models import FormatToExtensions
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.core.config import settings

SUPPORTED_SUFFIXES = {
    f".{ext}"
    for exts in FormatToExtensions.values()
    for ext in exts
}

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

logger = get_logger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG 知识库"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: SessionDep,
) -> Any:
    """
    上传文档，后台异步处理

    支持所有 Docling 可解析的格式（PDF、DOCX、PPTX、HTML、Markdown、图片、CSV、XLSX 等）。
    处理流程：上传 → Docling 解析 → 多模态回填 → 切片 → BGE-M3 向量化 → 入库
    """
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}，仅支持 {', '.join(sorted(SUPPORTED_SUFFIXES))}",
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

    background_tasks.add_task(rag_service.process_and_store, doc.id)

    return UploadResponse(document_id=doc.id, file_name=file.filename, status=DocumentStatus.PROCESSING)  # type: ignore[arg-type]


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
