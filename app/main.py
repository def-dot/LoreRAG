"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import access_log_middleware
from app.routers import auth, external_api, items, system, users, webhooks
from app.utils import init_sentry

logger = get_logger(__name__)


# ---------- lifespan：应用启动/关闭时执行 ----------
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    init_sentry()
    setup_logging()
    # try:
    #     import subprocess

    #     subprocess.check_call(["alembic", "upgrade", "head"])
    #     logger.info("%s started — DB migrated", settings.APP_NAME)
    # except Exception:
    #     logger.critical("Failed to initialize database", exc_info=True)
    #     raise
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    description="FastAPI Template — 用户认证与 CRUD 示例项目",
    docs_url="/docs" if settings.APP_ENV == "dev" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "dev" else None,
    swagger_ui_parameters={"persistAuthorization": True},
)

# ---------- 异常处理 ----------
register_exception_handlers(app)

# ---------- 中间件 ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(access_log_middleware)

# ---------- 注册路由 ----------
API_V1 = "/api/v1"
app.include_router(auth.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
app.include_router(items.router, prefix=API_V1)
app.include_router(external_api.router, prefix=API_V1)
app.include_router(webhooks.router)
app.include_router(system.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
