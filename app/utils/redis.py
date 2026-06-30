"""Redis 工具"""

import redis.asyncio as redis

from app.core.config import settings
<<<<<<< HEAD
from app.core.constants import PARSE_SLOTS_KEY
=======
>>>>>>> 0834f426b08b34b8cd07e4eafc07b28af3867e4d


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

    def __init__(self, key: str) -> None:
        self.key = key
        self.max_slots = 0

    async def init(self, max_slots: int) -> None:
        """预填令牌"""
        self.max_slots = max_slots
        r = redis_client()
        if await r.set(f"{self.key}:init", "1", nx=True, ex=10):
            await r.delete(self.key)
            await r.rpush(self.key, *[str(i) for i in range(1, self.max_slots + 1)])

    async def acquire(self, poll_seconds: int = 30) -> str:
        """BLPOP 阻塞等待"""
        r = redis_client()
        while True:
            result = await r.blpop(self.key, timeout=poll_seconds)
            if result is not None:
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
