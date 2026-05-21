"""数据库连接与会话管理"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DB_DEBUG,
    pool_size=20,
    max_overflow=10,
)


# 注册 pgvector 类型编解码（asyncpg 连接级别）
@event.listens_for(engine.sync_engine, "connect")
def _register_vector(dbapi_conn, _connection_record):
    try:
        from pgvector.asyncpg import register_vector

        # asyncpg 连接需要通过底层 loop 注册，这里仅在 sync 事件中标记
        # 实际编解码通过 pgvector.sqlalchemy.Vector 的 TypeDecorator 处理
        pass
    except ImportError:
        pass


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 依赖注入：获取数据库会话
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db
