from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Header, Request
from mip_api.config import get_settings
from mip_api.search import SearchService
from mip_database.session import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

_search_service: SearchService | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
        await _search_service.ensure_indices()
    return _search_service


async def get_tenant_id(
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
) -> UUID:
    settings = get_settings()
    if x_tenant_id:
        return UUID(x_tenant_id)
    return UUID(settings.default_tenant_id)
