"""API authentication and tenant isolation."""

import hashlib
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from mip_api.config import get_settings
from mip_database.models import ApiKey, AuditLog
from mip_database.session import async_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def authenticate_request(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> tuple[uuid.UUID, str]:
    settings = get_settings()

    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.active.is_(True))
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.tenant_id, api_key.role

    if x_tenant_id:
        return uuid.UUID(x_tenant_id), "viewer"

    return uuid.UUID(settings.default_tenant_id), "viewer"


async def audit_action(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            audit_id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )
    await session.flush()
