"""Unit tests for webhook SSRF protections."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from mip_alert_worker.worker import _webhook_url_is_safe
from mip_api.routes import _validate_alert_delivery_config


def test_validate_alert_requires_allowlist_in_production(monkeypatch):
    monkeypatch.setattr(
        "mip_api.routes.get_settings",
        lambda: SimpleNamespace(app_env="production", alert_webhook_allowed_hosts=""),
    )

    with pytest.raises(HTTPException) as exc:
        _validate_alert_delivery_config(
            ["webhook"],
            {"webhook": {"url": "https://hooks.example.com/alert"}},
        )

    assert exc.value.status_code == 400
    assert "ALERT_WEBHOOK_ALLOWED_HOSTS" in str(exc.value.detail)


def test_worker_rejects_webhook_without_allowlist_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALERT_WEBHOOK_ALLOWED_HOSTS", raising=False)
    monkeypatch.setattr(
        "mip_alert_worker.worker.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    assert not _webhook_url_is_safe("https://hooks.example.com/alert")


def test_worker_rejects_host_not_on_allowlist(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALERT_WEBHOOK_ALLOWED_HOSTS", "hooks.trusted.com")
    monkeypatch.setattr(
        "mip_alert_worker.worker.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    assert not _webhook_url_is_safe("https://hooks.example.com/alert")
