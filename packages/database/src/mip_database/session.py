from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mip_database.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


@lru_cache
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


class _AsyncSessionFactoryProxy:
    """Lazy proxy so importing database models does not connect at import time."""

    def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return get_async_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(get_async_session_factory(), name)


async_session_factory = _AsyncSessionFactoryProxy()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_async_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
