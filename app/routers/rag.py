"""RAG 知识库 API 路由"""

import asyncio
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import SessionDep
from app.core.logging import get_logger
from app.schemas.rag import (
    DeleteResponse,
    DocumentListResponse,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)
from app.services import rag as rag_service
from app.services.document import process_document

logger = get_logger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG 知识库"])


async def _process_and_store(file_path: str) -> None:
    """后台任务：解析文档 → 切片 → 计算向量 → 入库"""
    try:
        chunks = await asyncio.to_thread(process_document, file_path)
        if not chunks:
            logger.warning("No chunks produced from %s", file_path)
            return

        await rag_service.store_chunks(chunks)
        logger.info("Document processed successfully: %s (%d chunks)", file_path, len(chunks))
    except Exception:
        logger.exception("Failed to process document: %s", file_path)
    finally:
        # 清理上传文件
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: SessionDep,
) -> Any:
    """
    上传文档（PDF/DOCX/PPTX），后台异步处理

    处理流程：上传 → Docling 解析 → 多模态回填 → 切片 → BGE-M3 向量化 → 入库
    """
    suffixes = {".pdf", ".docx", ".pptx"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in suffixes:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}，仅支持 {', '.join(suffixes)}",
        )

    # 保存上传文件
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)  # type: ignore[arg-type]

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 后台异步处理
    background_tasks.add_task(_process_and_store, file_path)

    return UploadResponse(file_name=file.filename, status="processing")  # type: ignore[arg-type]


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
    """列出所有已入库的文档"""
    docs = await rag_service.list_documents(db)
    return DocumentListResponse(items=docs, total=len(docs))


@router.delete("/documents/{file_name}", response_model=DeleteResponse)
async def delete_document(
    file_name: str,
    db: SessionDep,
) -> Any:
    """删除指定文档的所有切片"""
    deleted = await rag_service.delete_document(file_name, db)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"文档不存在: {file_name}")
    return DeleteResponse(deleted_chunks=deleted, file_name=file_name)
