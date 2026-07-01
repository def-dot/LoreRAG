"""文档解析并发控制 — Redis 分布式信号量 + 可取消 + 启动恢复"""

import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.services.document import get_document, update_document_status
from app.services.chunk import insert_chunks
from app.core.config import settings
from app.core.constants import PARSE_SLOTS_KEY
from app.utils.redis import Mutex, Semaphore

logger = get_logger(__name__)

_semaphore = Semaphore(PARSE_SLOTS_KEY, settings.MAX_CONCURRENT)

# ---- 状态 ----
_tasks: dict[int, asyncio.Task] = {}  # doc_id → task

# worker 脚本路径
_WORKER_SCRIPT = str(Path(__file__).resolve().parent / "_chunk_worker.py")


def schedule(document_id: int) -> None:
    """文档上传后调用：创建独立任务抢信号量 → 解析"""
    task = asyncio.create_task(_run(document_id), name=f"parse-doc-{document_id}")
    _tasks[document_id] = task
    logger.info("Doc#%d scheduled", document_id)


async def _run(document_id: int) -> None:
    """文档解析-分块-入库"""
    slot: str | None = None
    try:
        slot = await _semaphore.acquire()

        # ---- 1. 读取文档信息 ----
        doc = await get_document(document_id)
        if doc is None:
            logger.warning("Doc#%d not found in DB, skip", document_id)
            return

        file_path = doc.file_path
        if not os.path.exists(file_path):
            await update_document_status(document_id, DocumentStatus.FAILED,
                                         error_message=f"源文件不存在: {file_path}")
            return

        await update_document_status(document_id, DocumentStatus.PROCESSING)

        # ---- 2. 文档解析 ----
        proc = await asyncio.create_subprocess_exec(
            sys.executable, _WORKER_SCRIPT, file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = stderr.decode(errors="replace")[-2000:]
                raise RuntimeError(f"解析失败: {err}")
            chunks = json.loads(stdout.decode())
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

        # ---- 3. 入库 ----
        inserted_count = 0
        if chunks:
            inserted_count = await insert_chunks(chunks, document_id=document_id)

        if inserted_count == 0:
            await update_document_status(document_id, DocumentStatus.FAILED,
                                         error_message="切片失败")
            return

        await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=inserted_count)

    except asyncio.CancelledError:
        await update_document_status(document_id, DocumentStatus.FAILED, error_message="用户取消")
    except Exception as exc:
        await update_document_status(document_id, DocumentStatus.FAILED,
                                     error_message=str(exc)[:2000])
    finally:
        _tasks.pop(document_id, None)
        if slot is not None:
            await _semaphore.release(slot)


async def recover_stuck() -> int:
    """
    扫描 DB 中卡在 PENDING / PROCESSING 的文档，重新调度。
    SET NX 防止多 worker 重复调度同一文档。
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING])
            )
        )
        stuck = result.scalars().all()

    scheduled = 0
    for doc in stuck:
        if await Mutex(f"recover:lock:{doc.id}").try_acquire():
            schedule(doc.id)
            scheduled += 1

    if scheduled:
        logger.info("Recovered %d stuck document(s), re-scheduled (total stuck=%d)", scheduled, len(stuck))
    return scheduled


async def cancel_and_await(document_id: int) -> bool:
    """取消指定文档的解析并等待完成"""
    task = _tasks.get(document_id)
    if task is None:
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return True
