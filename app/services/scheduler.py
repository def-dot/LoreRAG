"""文档解析并发控制 — Redis 分布式信号量 + 重试 + 可取消 + 启动恢复"""

import asyncio
import os

import redis.asyncio as redis
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.services.document import get_document, update_document_status
from app.services.rag_chunk import document_chunk
from app.services.chunk import insert_chunks

logger = get_logger(__name__)

# ---- 配置 ----
MAX_CONCURRENT = 2       # 同时解析数（跨 worker 全局生效）
MAX_RETRIES = 3           # 最大重试次数
RETRY_DELAY_BASE = 5      # 退避基数（秒），指数递增: 5 → 10 → 20
SLOT_TTL = 600            # 槽位锁 TTL（秒），超时自动释放防死锁

# ---- 状态 ----
_tasks: dict[int, asyncio.Task] = {}  # doc_id → task（所有未完成的）
_active: set[int] = set()             # 正在解析的文档


_SLOT_KEYS = [f"parse:slot:{i}" for i in range(1, MAX_CONCURRENT + 1)]

# 共享连接池（lifespan 启动时调用 _init_redis）
_pool: redis.ConnectionPool | None = None


async def _init_redis() -> None:
    """初始化 Redis 连接池"""
    global _pool
    _pool = redis.ConnectionPool.from_url(settings.REDIS_URL, max_connections=MAX_CONCURRENT + 4)


def status() -> dict:
    """文档解析状态（仅当前 worker）"""
    waiting_doc_ids = sorted(set(_tasks.keys()) - _active)
    active_doc_ids = sorted(_active)
    return {
        "waiting": waiting_doc_ids,
        "waiting_count": len(waiting_doc_ids),
        "active": active_doc_ids,
        "active_count": len(active_doc_ids),
        "max_concurrent": MAX_CONCURRENT,
        "max_retries": MAX_RETRIES,
    }


def schedule(document_id: int) -> None:
    """文档上传后调用：创建独立任务抢信号量 → 解析"""
    task = asyncio.create_task(
        _run(document_id),
        name=f"parse-doc-{document_id}",
    )
    _tasks[document_id] = task
    task.add_done_callback(
        lambda _t, did=document_id, t=task: _tasks.pop(did, None) if _tasks.get(did) is t else None
    )
    state = status()
    logger.info("Doc#%d scheduled — waiting=%d, active=%d",
                document_id, state["waiting_count"], state["active_count"])


def cancel(document_id: int) -> bool:
    """取消指定文档的解析任务"""
    task = _tasks.get(document_id)
    if task is None:
        return False
    task.cancel()
    logger.info("Doc#%d cancel requested", document_id)
    return True


# ========== 核心 ==========


async def _run(document_id: int) -> None:
    """Redis 分布式信号量限流 → 解析 → 释放"""
    r = redis.Redis(connection_pool=_pool)
    slot: str | None = None
    try:
        while slot is None:
            for key in _SLOT_KEYS:
                if await r.set(key, str(document_id), nx=True, ex=SLOT_TTL):
                    slot = key
                    break
            if slot is None:
                await asyncio.sleep(1)

        _active.add(document_id)
        try:
            await _process_one(document_id)
        finally:
            _active.discard(document_id)
            if slot:
                await r.delete(slot)
    except asyncio.CancelledError:
        await update_document_status(document_id, DocumentStatus.FAILED, error_message="用户取消")
        logger.info("Doc#%d cancelled", document_id)
        raise
    except Exception as exc:
        # ---- 3. 重试 / 彻底失败 ----
        doc = await get_document(document_id)
        retry = (doc.retry_count or 0) + 1 if doc else 1

        if retry <= MAX_RETRIES:
            delay = RETRY_DELAY_BASE * (2 ** (retry - 1))
            logger.warning("Doc#%d failed, retry %d/%d in %ds: %s",
                           document_id, retry, MAX_RETRIES, delay, exc)

            await update_document_status(document_id, DocumentStatus.PENDING,
                                         error_message=str(exc)[:2000], retry_count=retry)

            await asyncio.sleep(delay)
            schedule(document_id)
        else:
            logger.error("Doc#%d permanently failed after %d retries: %s",
                         document_id, retry, exc)

            await update_document_status(document_id, DocumentStatus.FAILED,
                                         error_message=str(exc)[:2000], retry_count=retry)


async def _process_one(document_id: int) -> None:
    """单个文档的完整解析管线，含重试和详细错误处理"""
    # ---- 1. 读取文档信息 ----
    doc = await get_document(document_id)
    if doc is None:
        logger.warning("Doc#%d not found in DB, skip", document_id)
        return

    file_path = doc.file_path
    # 检查文件是否存在
    if not os.path.exists(file_path):
        error_msg = f"源文件不存在: {file_path}"
        logger.error("Doc#%d: %s", document_id, error_msg)
        await update_document_status(document_id, DocumentStatus.FAILED, error_message=error_msg)
        return

    await update_document_status(document_id, DocumentStatus.PROCESSING)

    # ---- 2. 解析 + 入库 ----
    logger.info("Doc#%d: starting parsing", document_id)
    chunks = await asyncio.to_thread(document_chunk, file_path)

    inserted_count = 0
    if chunks:
        logger.info("Doc#%d: parsed %d chunks, inserting into database", document_id, len(chunks))
        inserted_count = await insert_chunks(chunks, document_id=document_id)

    if inserted_count == 0:
        logger.warning("Doc#%d: 没有成功存储任何切片 chunks count: %d, inserted count: %d", document_id, len(chunks), inserted_count)
        await update_document_status(document_id, DocumentStatus.FAILED,
                                        error_message="没有成功存储任何切片，数据库写入失败")
        return

    await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=inserted_count)
    logger.info("Doc#%d completed: %d chunks stored", document_id, inserted_count)

# ========== 启动恢复 ==========


async def recover_stuck() -> int:
    """
    扫描 DB 中卡在 PENDING / PROCESSING 的文档，重新调度。
    在 lifespan 启动时调用，应对服务重启丢失内存状态。
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING])
            )
        )
        stuck = result.scalars().all()

    for doc in stuck:
        schedule(doc.id)

    if stuck:
        logger.info("Recovered %d stuck document(s), re-scheduled", len(stuck))
    return len(stuck)
