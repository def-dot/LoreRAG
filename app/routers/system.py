"""健康检查路由"""

from typing import Any

from fastapi import APIRouter

from app.core.response import UnifiedResponseRoute

router = APIRouter(tags=["系统"], route_class=UnifiedResponseRoute)


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> Any:
    return {"status": "ssss"}
