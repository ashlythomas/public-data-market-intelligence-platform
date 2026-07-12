"""Alert delivery worker."""

import ipaddress
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from mip_database.models import AlertDelivery
from mip_database.session import async_session_factory
from mip_observability import setup_logging

logger = logging.getLogger(__name__)


def _webhook_url_is_safe(url: str) -> bool:
    parsed = urlparse(url.strip())
    is_development = os.environ.get("APP_ENV", "production") == "development"
    allow_http = is_development
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if parsed.scheme.lower() not in allowed_schemes or not parsed.hostname:
        return False

    allowed_hosts = {
        host.strip().lower()
        for host in os.environ.get("ALERT_WEBHOOK_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    if not is_development and not allowed_hosts:
        return False
    hostname = parsed.hostname.lower()
    if allowed_hosts and hostname not in allowed_hosts:
        return False

    try:
        addr_info = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return False

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


async def deliver_webhook(url: str, payload: dict[str, Any]) -> bool:
    if not _webhook_url_is_safe(url):
        raise ValueError("unsafe webhook URL")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        response = await client.post(url, json=payload)
        return response.is_success


async def deliver_email(to: str, payload: dict[str, Any]) -> bool:
    logger.info("Email delivery (mock): to=%s subject=%s", to, payload.get("subject"))
    return True


async def process_alert_candidate(message: dict[str, Any]) -> None:
    setup_logging()
    payload = message.get("payload", message)
    alert_id = payload.get("alert_id")
    channel = payload.get("channel", "email")
    delivery_payload = payload.get("delivery_payload", {})

    delivery = AlertDelivery(
        delivery_id=uuid4(),
        alert_id=alert_id,
        channel=channel,
        status="pending",
        payload=delivery_payload,
    )

    success = False
    error_message = None
    try:
        if channel == "webhook":
            success = await deliver_webhook(payload.get("webhook_url", ""), delivery_payload)
        elif channel == "email":
            success = await deliver_email(payload.get("email", ""), delivery_payload)
        else:
            success = True
    except Exception as e:
        error_message = str(e)
        logger.exception("Alert delivery failed")

    delivery.status = "delivered" if success else "failed"
    delivery.delivered_at = datetime.now(UTC) if success else None
    delivery.error_message = error_message

    async with async_session_factory() as session:
        session.add(delivery)
        await session.commit()
