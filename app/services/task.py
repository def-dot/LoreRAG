"""文档解析并发控制 — Semaphore 限流 + 重试 + 可取消 + 启动恢复"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.services.document import get_document, update_document_status
from app.services.rag_chunk import document_chunk
from app.services.chunk import insert_chunks

logger = get_logger(__name__)

# ---- 配置 ----
MAX_CONCURRENT = 2       # 同时解析数
MAX_RETRIES = 3           # 最大重试次数
RETRY_DELAY_BASE = 5      # 退避基数（秒），指数递增: 5 → 10 → 20

# ---- 状态 ----
_sem = asyncio.Semaphore(MAX_CONCURRENT)
_tasks: dict[int, asyncio.Task] = {}  # doc_id → task（所有未完成的）
_active: set[int] = set()             # 正在解析的文档


def status() -> dict:
    """文档解析状态"""
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
    """
    文档上传后调用：创建独立任务抢信号量 → 解析。
    """
    task = asyncio.create_task(
        _run_with_semaphore(document_id),
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
    """
    取消指定文档的解析任务。
    """
    task = _tasks.get(document_id)
    if task is None:
        return False

    task.cancel()
    logger.info("Doc#%d cancel requested", document_id)
    return True


# ========== 核心 ==========


async def _run_with_semaphore(document_id: int) -> None:
    """抢到信号量 → 解析 → 释放"""
    try:
        async with _sem:
            _active.add(document_id)
            try:
                await _process_one(document_id)
            finally:
                _active.discard(document_id)
    except asyncio.CancelledError:
        await update_document_status(document_id, DocumentStatus.FAILED, error_message="用户取消")
        logger.info("Doc#%d cancelled", document_id)
        raise
    except Exception:
        logger.exception("Doc#%d crashed unexpectedly", document_id)


async def _process_one(document_id: int) -> None:
    """单个文档的完整解析管线，含重试"""
    # ---- 1. 读取文档信息 ----
    doc = await get_document(document_id)
    if doc is None:
        logger.warning("Doc#%d not found in DB, skip", document_id)
        return
    file_path = doc.file_path

    await update_document_status(document_id, DocumentStatus.PROCESSING)

    # ---- 2. 解析 + 入库 ----
    try:
        chunks = await asyncio.to_thread(document_chunk, file_path)

        count = 0 if not chunks else await insert_chunks(chunks, document_id=document_id)

        await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=count)

        logger.info("Doc#%d completed: %d chunks", document_id, count)

    except asyncio.CancelledError:
        raise  # 交给外层 _run_with_semaphore 处理

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
