"""GDELT lastupdate export connector."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from mip_connector_fed.base import BaseConnector, RawPayload, SourceItem

GDELT_LASTUPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
GDELT_BASE = "http://data.gdeltproject.org/gdeltv2/"


class GdeltConnector(BaseConnector):
    connector_name = "gdelt"
    connector_version = "0.1.0"
    source_id = "gdelt"

    async def discover(self, checkpoint: dict[str, Any] | None = None) -> AsyncIterator[SourceItem]:
        self.load_checkpoint(checkpoint)
        self._seen_urls: set[str] = set(self._checkpoint.get("seen_urls", []))

        response = await self.client.get(GDELT_LASTUPDATE)
        response.raise_for_status()
        lines = response.text.strip().splitlines()

        for line in lines[-5:]:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            filename = parts[2]
            if not filename.endswith(".export.CSV.zip"):
                continue
            url = f"{GDELT_BASE}{filename}"
            if url in self._seen_urls:
                continue
            yield SourceItem(
                external_id=filename.replace(".export.CSV.zip", ""),
                url=url,
                published_at=datetime.now(UTC),
                metadata={"filename": filename, "format": "export_csv_zip"},
            )

        self._checkpoint["last_discover_at"] = datetime.now(UTC).isoformat()

    def mark_processed(self, item: SourceItem) -> None:
        self._seen_urls.add(item.url)
        self._checkpoint["seen_urls"] = list(self._seen_urls)[-200:]

    async def fetch(self, item: SourceItem) -> RawPayload:
        response = await self.client.get(item.url)
        response.raise_for_status()
        return RawPayload(
            content=response.content,
            content_type="application/zip",
            source_url=item.url,
            external_id=item.external_id,
            published_at=item.published_at,
            metadata=item.metadata,
        )
