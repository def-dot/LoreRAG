"""RAG 知识库 API 路由"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException


from app.core.deps import SessionDep
from app.core.logging import get_logger
from app.core.response import UnifiedResponseRoute
from app.schemas.rag import (
    SearchRequest,
    SearchResponse,
)
from app.services import rag_query
from app.services.scheduler import cancel_and_await

logger = get_logger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG 知识库"], route_class=UnifiedResponseRoute)


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    req: SearchRequest,
) -> Any:
    """
    知识库检索

    使用稠密向量 + 全文检索 RRF 融合，返回最相关的文档切片。
    """
    results = await rag_query.search(req.query, req.top_k)
    return SearchResponse(results=results, total=len(results))


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
    ok = await cancel_and_await(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"文档不在解析队列中: {document_id}")
    return {"document_id": document_id, "cancelled": True}
