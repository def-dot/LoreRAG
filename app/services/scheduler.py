"""文档解析并发控制 — Redis 分布式信号量 + 重试 + 可取消 + 启动恢复"""

import asyncio
import json
import os
import sys
from pathlib import Path

import redis.asyncio as redis
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.services.document import get_document, update_document_status
from app.services.chunk import insert_chunks

logger = get_logger(__name__)

# ---- 配置 ----
MAX_CONCURRENT = 2       # 同时解析数（跨 worker 全局生效）
MAX_RETRIES = 3           # 最大重试次数
RETRY_DELAY_BASE = 5      # 退避基数（秒），指数递增: 5 → 10 → 20

# ---- 状态 ----
_tasks: dict[int, asyncio.Task] = {}  # doc_id → task（所有未完成的）
_active: set[int] = set()             # 正在解析的文档
_parsing: dict[int, asyncio.subprocess.Process] = {}  # doc_id → 正在运行的解析子进程

# worker 脚本路径
_WORKER_SCRIPT = str(Path(__file__).resolve().parent / "_chunk_worker.py")


_SLOT_KEY = "parse:slots"

# 共享连接池（lifespan 启动时调用 _init_redis）
_pool: redis.ConnectionPool | None = None


async def _init_redis() -> None:
    """初始化 Redis 连接池并预填信号量令牌（多 worker 安全：SET NX 保证只填一次）"""
    global _pool
    _pool = redis.ConnectionPool.from_url(settings.REDIS_URL, max_connections=50)
    r = redis.Redis(connection_pool=_pool)
    if await r.set("parse:slots:init", "1", nx=True, ex=10):
        await r.delete(_SLOT_KEY)
        await r.rpush(_SLOT_KEY, *[str(i) for i in range(1, MAX_CONCURRENT + 1)])


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

    def _on_done(_finished: asyncio.Task) -> None:
        if _tasks.get(document_id) is task:
            _tasks.pop(document_id, None)

    task.add_done_callback(_on_done)
    state = status()
    logger.info("Doc#%d scheduled — waiting=%d, active=%d",
                document_id, state["waiting_count"], state["active_count"])


def cancel(document_id: int) -> bool:
    """取消指定文档的解析任务（不等待任务结束）"""
    task = _tasks.get(document_id)
    if task is None:
        return False
    task.cancel()
    logger.info("Doc#%d cancel requested", document_id)
    return True


async def cancel_and_await(document_id: int) -> bool:
    """取消指定文档的解析任务并等待其完成"""
    task = _tasks.get(document_id)
    if task is None:
        return False
    task.cancel()
    logger.info("Doc#%d cancel requested (awaiting completion)", document_id)
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Doc#%d task finished after cancel", document_id)
    return True


# ========== 核心 ==========
async def _run(document_id: int) -> None:
    """Redis 分布式信号量限流 → 解析 → 释放"""
    r = redis.Redis(connection_pool=_pool)
    slot: str | None = None
    try:
        # BLPOP 阻塞等待可用槽位，每 30s 超时检查取消信号
        while slot is None:
            result = await r.blpop(_SLOT_KEY, timeout=30)
            if result is not None:
                _, slot = result  # (key, value)

        _active.add(document_id)
        try:
            await _process_one(document_id)
        finally:
            _active.discard(document_id)
            if slot:
                try:
                    await r.rpush(_SLOT_KEY, slot)
                except redis.RedisError:
                    pass
    except asyncio.CancelledError:
        await update_document_status(document_id, DocumentStatus.FAILED, error_message="用户取消")
        logger.info("Doc#%d cancelled", document_id)
    except Exception as exc:
        # ---- 重试 / 彻底失败 ----
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
    """单个文档的完整解析管线（子进程解析，可被 kill 强杀）"""
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

    # ---- 2. 子进程解析 ----
    logger.info("Doc#%d: starting parsing (subprocess)", document_id)
    chunks: list[dict] = []
    proc = await asyncio.create_subprocess_exec(
        sys.executable, _WORKER_SCRIPT, file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _parsing[document_id] = proc
    try:
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"解析失败: {stderr.decode(errors='replace')[:2000]}")

        chunks = json.loads(stdout.decode())
    except asyncio.CancelledError:
        _kill_process(document_id)
        raise
    finally:
        _parsing.pop(document_id, None)

    # ---- 3. 入库 ----
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


def _kill_process(document_id: int) -> None:
    """强行终止指定文档的解析子进程（cancel 回调）"""
    proc = _parsing.pop(document_id, None)
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    logger.info("Doc#%d parse subprocess killed", document_id)

# ========== 启动恢复 ==========


async def recover_stuck() -> int:
    """
    扫描 DB 中卡在 PENDING / PROCESSING 的文档，重新调度。
    在 lifespan 启动时调用，应对服务重启丢失内存状态。
    SET NX 防止多 worker 重复调度同一文档。
    """
    r = redis.Redis(connection_pool=_pool)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING])
            )
        )
        stuck = result.scalars().all()

    scheduled = 0
    for doc in stuck:
        if await r.set(f"recover:lock:{doc.id}", "1", nx=True, ex=60):
            schedule(doc.id)
            scheduled += 1

    if scheduled:
        logger.info("Recovered %d stuck document(s), re-scheduled (total stuck=%d)", scheduled, len(stuck))
    return scheduled
