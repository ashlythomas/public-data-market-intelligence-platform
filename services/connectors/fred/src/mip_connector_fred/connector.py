"""FRED press releases and economic data connector."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from mip_connector_fed.base import BaseConnector, RawPayload, SourceItem

FRED_PRESS_RSS = "https://fred.stlouisfed.org/feeds/fred_press.xml"


class FredConnector(BaseConnector):
    connector_name = "fred"
    connector_version = "0.1.0"
    source_id = "fred"

    async def discover(self, checkpoint: dict[str, Any] | None = None) -> AsyncIterator[SourceItem]:
        self.load_checkpoint(checkpoint)
        self._seen_urls: set[str] = set(self._checkpoint.get("seen_urls", []))

        response = await self.client.get(FRED_PRESS_RSS)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        for entry in feed.entries:
            url = entry.get("link", "")
            if not url or url in self._seen_urls:
                continue
            published_at = None
            if entry.get("published"):
                try:
                    published_at = parsedate_to_datetime(entry.published).replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    pass
            external_id = entry.get("id", url)
            yield SourceItem(
                external_id=external_id,
                url=url,
                published_at=published_at,
                metadata={"title": entry.get("title", "")},
            )

        self._checkpoint["last_discover_at"] = datetime.now(UTC).isoformat()

    def mark_processed(self, item: SourceItem) -> None:
        self._seen_urls.add(item.url)
        self._checkpoint["seen_urls"] = list(self._seen_urls)[-500:]

    async def fetch(self, item: SourceItem) -> RawPayload:
        response = await self.client.get(item.url)
        response.raise_for_status()
        return RawPayload(
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
            source_url=item.url,
            external_id=item.external_id,
            published_at=item.published_at,
            metadata=item.metadata,
        )
