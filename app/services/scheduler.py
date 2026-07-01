"""文档解析并发控制 — Redis 分布式信号量 + 可取消 + 启动恢复"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.constants import PARSE_SLOTS_KEY, RECOVER_LOCK_KEY
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.services.document import get_document, update_document_status
from app.services.chunk import insert_chunks
from app.utils.redis import Mutex, Semaphore

logger = get_logger(__name__)

_semaphore = Semaphore(PARSE_SLOTS_KEY, settings.MAX_CONCURRENT)

_tasks: dict[int, asyncio.Task] = {}  # doc_id → task

# 文档解析脚本
_PARSE_SCRIPT = str(Path(__file__).resolve().parent / "rag_chunk.py")


def schedule(document_id: int) -> None:
    """文档上传后调用：创建独立任务抢信号量 → 解析"""
    task = asyncio.create_task(_run(document_id), name=f"parse-doc-{document_id}")
    _tasks[document_id] = task
    logger.info("Doc#%d scheduled", document_id)


async def _run(document_id: int) -> None:
    """文档解析-分块-入库"""
    slot: str | None = None
    proc = None
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
        output_fd, output_path = tempfile.mkstemp(suffix=".json")
        os.close(output_fd)

        proc = await asyncio.create_subprocess_exec(
            sys.executable, _PARSE_SCRIPT, file_path, "--output", output_path,
        )
        try:
            await proc.communicate()

            with open(output_path, encoding="utf-8") as f:
                result = json.load(f)
            if not result["ok"]:
                raise RuntimeError(f"解析失败: {result['error']}")
            chunks = result["data"]
        finally:
            os.remove(output_path)

        # ---- 3. 入库 ----
        if not chunks:
            await update_document_status(document_id, DocumentStatus.FAILED,
                                         error_message="未解析出文本块")
            return

        inserted_count = await insert_chunks(chunks, document_id=document_id)
        if inserted_count == 0:
            await update_document_status(document_id, DocumentStatus.FAILED,
                                         error_message="文本块入库失败")
            return

        await update_document_status(document_id, DocumentStatus.COMPLETED, chunk_count=inserted_count)

    except asyncio.CancelledError:
        if proc is not None and proc.returncode is None:
            # 终止解析子进程
            proc.kill()
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

    for doc in stuck:
        if await Mutex(f"{RECOVER_LOCK_KEY}:{doc.id}").try_acquire():
            schedule(doc.id)
            logger.info("Recovered stuck document: %d", doc.id)


async def cancel_and_await(document_id: int) -> bool:
    """取消指定文档的解析，并等待完成"""
    task = _tasks.get(document_id)
    if task is None:
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return True
