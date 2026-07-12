"""Pagination and query helpers."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def count_query(session: AsyncSession, query: Select[Any]) -> int:
    """Count rows for a select query without materializing all results."""
    count_stmt = select(func.count()).select_from(query.subquery())
    result = await session.execute(count_stmt)
    return int(result.scalar_one())
