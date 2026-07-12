from collections.abc import AsyncGenerator

from fastapi import Request
from mip_api.search import SearchService
from mip_database.session import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

_search_service: SearchService | None = None


def set_search_service(service: SearchService) -> None:
    global _search_service
    _search_service = service


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_search_service(request: Request) -> SearchService:
    """Return the SearchService from app lifespan, falling back to module singleton."""
    service = getattr(request.app.state, "search_service", None) or _search_service
    if service is None:
        service = SearchService()
        await service.ensure_indices()
        set_search_service(service)
    return service
