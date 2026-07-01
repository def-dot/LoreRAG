"""Redis 工具"""

import redis.asyncio as redis

from app.core.config import settings
from app.core.constants import PARSE_SLOTS_KEY

_pool: redis.ConnectionPool | None = None


def redis_client() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL, max_connections=50
        )
    return redis.Redis(connection_pool=_pool)

class Semaphore:
    """分布式信号量 — BLPOP/RPUSH 实现的 FIFO 公平队列"""

    def __init__(self, key: str, max_slots: int) -> None:
        self.key = key
        self.max_slots = max_slots
        self._initialized = False

    async def _ensure_init(self) -> None:
        """首次 acquire 时预填令牌"""
        if self._initialized:
            return
        r = redis_client()
        if await r.set(f"{self.key}:init", "1", nx=True, ex=10):
            await r.delete(self.key)
            await r.rpush(self.key, *[str(i) for i in range(1, self.max_slots + 1)])
        self._initialized = True

    async def acquire(self) -> str:
        """BLPOP 无限阻塞等待"""
        await self._ensure_init()
        r = redis_client()
        result = await r.blpop(self.key)
        return result[1]

    async def release(self, slot: str) -> None:
        """归还槽位"""
        try:
            r = redis_client()
            await r.rpush(self.key, slot)
        except redis.RedisError:
            pass


class Mutex:
    """分布式互斥锁 — SET NX + TTL"""

    def __init__(self, key: str, ttl: int = 60) -> None:
        self.key = key
        self.ttl = ttl

    async def try_acquire(self) -> bool:
        r = redis_client()
        return bool(await r.set(self.key, "1", nx=True, ex=self.ttl))
