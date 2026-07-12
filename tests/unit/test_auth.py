"""Unit tests for API authentication."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from mip_api.auth import AuthContext, authenticate_request, hash_api_key, require_role


@pytest.mark.asyncio
async def test_authenticate_development_fallback():
    request = MagicMock()
    request.state = MagicMock()
    session = AsyncMock()

    with patch("mip_api.auth.get_settings") as mock_settings:
        mock_settings.return_value.app_env = "development"
        mock_settings.return_value.allow_dev_auth = True
        mock_settings.return_value.default_tenant_id = "00000000-0000-0000-0000-000000000001"

        auth = await authenticate_request(request, session=session, x_api_key=None)

    assert isinstance(auth, AuthContext)
    assert auth.tenant_id == uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert auth.role == "analyst"


@pytest.mark.asyncio
async def test_authenticate_development_fails_closed_without_explicit_flag():
    request = MagicMock()
    request.state = MagicMock()
    session = AsyncMock()

    with patch("mip_api.auth.get_settings") as mock_settings:
        mock_settings.return_value.app_env = "development"
        mock_settings.return_value.allow_dev_auth = False
        with pytest.raises(HTTPException) as exc:
            await authenticate_request(request, session=session, x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_requires_api_key_in_production():
    request = MagicMock()
    request.state = MagicMock()
    session = AsyncMock()

    with patch("mip_api.auth.get_settings") as mock_settings:
        mock_settings.return_value.app_env = "production"
        with pytest.raises(HTTPException) as exc:
            await authenticate_request(request, session=session, x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_allows_admin():
    check = require_role("analyst")
    auth = AuthContext(tenant_id=uuid.uuid4(), role="admin")
    result = await check(auth=auth)
    assert result.role == "admin"


@pytest.mark.asyncio
async def test_require_role_denies_viewer():
    check = require_role("analyst")
    auth = AuthContext(tenant_id=uuid.uuid4(), role="viewer")
    with pytest.raises(HTTPException) as exc:
        await check(auth=auth)
    assert exc.value.status_code == 403


def test_hash_api_key_deterministic():
    assert hash_api_key("test-key") == hash_api_key("test-key")
    assert hash_api_key("test-key") != hash_api_key("other-key")
