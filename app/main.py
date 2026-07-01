"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import access_log_middleware
from app.routers import auth, document, external_api, items, rag, system, users, webhooks
from app.services.scheduler import recover_stuck

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # init_sentry()
    setup_logging()
    await recover_stuck()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    description="LoreRAG — 生产级RAG问答系统",
    docs_url="/docs" if settings.APP_ENV == "dev" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "dev" else None,
    swagger_ui_parameters={"persistAuthorization": True},
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(access_log_middleware)

API_V1 = "/api/v1"
app.include_router(auth.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
app.include_router(items.router, prefix=API_V1)
app.include_router(external_api.router, prefix=API_V1)
app.include_router(rag.router, prefix=API_V1)
app.include_router(document.router, prefix=API_V1)
app.include_router(webhooks.router)
app.include_router(system.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
