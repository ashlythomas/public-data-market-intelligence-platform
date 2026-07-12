"""Connector SDK - base interfaces and utilities."""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SourceItem:
    external_id: str
    url: str
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPayload:
    content: bytes
    content_type: str
    source_url: str
    external_id: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector(ABC):
    connector_name: str = "base"
    connector_version: str = "0.1.0"
    source_id: str = "unknown"

    def __init__(self, *, timeout: float = 30.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self._checkpoint: dict[str, Any] = {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseConnector":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "MIP-Connector/0.1.0"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Connector not initialized. Use async context manager.")
        return self._client

    def load_checkpoint(self, checkpoint: dict[str, Any] | None) -> None:
        self._checkpoint = checkpoint or {}

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint.copy()

    @abstractmethod
    async def discover(self, checkpoint: dict[str, Any] | None = None) -> AsyncIterator[SourceItem]:
        ...

    @abstractmethod
    async def fetch(self, item: SourceItem) -> RawPayload:
        ...

    async def fetch_with_retry(self, item: SourceItem) -> RawPayload:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await self.fetch(item)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                wait = 2**attempt
                logger.warning(
                    "Fetch retry %d/%d for %s: %s",
                    attempt + 1,
                    self.max_retries,
                    item.url,
                    e,
                )
                await asyncio.sleep(wait)
        raise last_error or RuntimeError("Fetch failed")

    @staticmethod
    def content_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def build_envelope(
        self,
        payload: RawPayload,
        object_store_uri: str,
        ingestion_id: UUID | None = None,
    ) -> dict[str, Any]:
        ingestion_id = ingestion_id or uuid4()
        return {
            "ingestion_id": str(ingestion_id),
            "source_id": self.source_id,
            "external_id": payload.external_id,
            "source_url": payload.source_url,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "published_at": payload.published_at.isoformat() if payload.published_at else None,
            "content_type": payload.content_type,
            "object_store_uri": object_store_uri,
            "content_hash": self.content_hash(payload.content),
            "connector_version": self.connector_version,
            "metadata": payload.metadata,
        }
