"""API authentication and tenant isolation."""

import hashlib
import time
import uuid
from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import Depends, Header, HTTPException, Request
from mip_api.config import get_settings
from mip_api.deps import get_db
from mip_database.models import ApiKey, AuditLog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

RATE_LIMIT_WINDOW_SECONDS = 60
_redis_client: redis.Redis | None = None


@dataclass(frozen=True)
class AuthContext:
    tenant_id: uuid.UUID
    role: str


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def authenticate_request(
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
) -> AuthContext:
    """Authenticate via API key. In development, fall back to default tenant."""
    settings = get_settings()

    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.active.is_(True))
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        limiter = _get_redis_client()
        bucket_key = f"api-rate:{key_hash}:{int(time.time()) // RATE_LIMIT_WINDOW_SECONDS}"
        try:
            count = await limiter.incr(bucket_key)
            if count == 1:
                await limiter.expire(bucket_key, RATE_LIMIT_WINDOW_SECONDS)
        except redis.RedisError as exc:  # pragma: no cover - network failures are environment-specific
            raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
        if count > api_key.rate_limit:
            raise HTTPException(status_code=429, detail="API key rate limit exceeded")

        request.state.tenant_id = str(api_key.tenant_id)
        request.state.role = api_key.role
        return AuthContext(tenant_id=api_key.tenant_id, role=api_key.role)

    if settings.app_env == "development" and settings.allow_dev_auth:
        tenant_id = uuid.UUID(settings.default_tenant_id)
        request.state.tenant_id = str(tenant_id)
        request.state.role = "analyst"
        return AuthContext(tenant_id=tenant_id, role="analyst")

    raise HTTPException(
        status_code=401,
        detail="API key required. Pass X-Api-Key header.",
    )


def require_role(*allowed_roles: str):
    """Dependency factory to enforce role-based access."""

    async def _check(auth: AuthContext = Depends(authenticate_request)) -> AuthContext:
        if auth.role not in allowed_roles and auth.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return auth

    return _check


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
