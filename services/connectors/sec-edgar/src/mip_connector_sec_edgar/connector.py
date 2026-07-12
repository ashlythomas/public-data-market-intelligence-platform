"""SEC EDGAR 8-K and 10-K filing connector."""

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup
from mip_connector_fed.base import BaseConnector, RawPayload, SourceItem

SEC_FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-k&count=40&output=atom"
)
SEC_BASE = "https://www.sec.gov"


class SecEdgarConnector(BaseConnector):
    connector_name = "sec-edgar"
    connector_version = "0.1.0"
    source_id = "sec-edgar"

    async def discover(self, checkpoint: dict[str, Any] | None = None) -> AsyncIterator[SourceItem]:
        self.load_checkpoint(checkpoint)
        seen_urls: set[str] = set(self._checkpoint.get("seen_urls", []))

        response = await self.client.get(
            SEC_FEED,
            headers={"User-Agent": "MarketIntelligencePlatform contact@example.com"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "xml")

        for entry in soup.find_all("entry"):
            link = entry.find("link")
            if not link or not link.get("href"):
                continue
            url = link["href"]
            if url in seen_urls:
                continue
            title_tag = entry.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            updated_tag = entry.find("updated")
            published_at = None
            if updated_tag:
                try:
                    published_at = datetime.fromisoformat(
                        updated_tag.get_text(strip=True).replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            match = re.search(r"accession-number=(\d+-\d+-\d+)", url)
            external_id = match.group(1) if match else url.split("/")[-1]
            seen_urls.add(url)
            yield SourceItem(
                external_id=external_id,
                url=url,
                published_at=published_at,
                metadata={"title": title, "form_type": "8-K"},
            )

        self._checkpoint["seen_urls"] = list(seen_urls)[-500:]
        self._checkpoint["last_discover_at"] = datetime.now(UTC).isoformat()

    async def fetch(self, item: SourceItem) -> RawPayload:
        response = await self.client.get(
            item.url,
            headers={"User-Agent": "MarketIntelligencePlatform contact@example.com"},
        )
        response.raise_for_status()
        return RawPayload(
            content=response.content,
            content_type=response.headers.get("content-type", "text/html"),
            source_url=item.url,
            external_id=item.external_id,
            published_at=item.published_at,
            metadata=item.metadata,
        )
