"""Federal Reserve press release connector."""

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from mip_connector_fed.base import BaseConnector, RawPayload, SourceItem

logger = logging.getLogger(__name__)

FED_PRESS_URL = "https://www.federalreserve.gov/newsevents/pressreleases.htm"
FED_BASE_URL = "https://www.federalreserve.gov"


class FedConnector(BaseConnector):
    connector_name = "fed"
    connector_version = "0.1.0"
    source_id = "fed"

    async def discover(self, checkpoint: dict[str, Any] | None = None) -> AsyncIterator[SourceItem]:
        self.load_checkpoint(checkpoint)
        self._seen_urls: set[str] = set(self._checkpoint.get("seen_urls", []))

        response = await self.client.get(FED_PRESS_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        for row in soup.select("div.row"):
            link = row.select_one("a")
            if not link or not link.get("href"):
                continue
            href = link["href"]
            if "pressreleases" not in href:
                continue
            url = urljoin(FED_BASE_URL, href)
            if url in self._seen_urls:
                continue

            date_elem = row.select_one(".col-md-3, .result__date, time")
            published_at = None
            if date_elem:
                published_at = self._parse_date(date_elem.get_text(strip=True))

            title = link.get_text(strip=True)
            external_id = self._extract_id(href)

            yield SourceItem(
                external_id=external_id,
                url=url,
                published_at=published_at,
                metadata={"title": title},
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

    @staticmethod
    def _extract_id(href: str) -> str:
        match = re.search(r"pressreleases/(\w+)", href)
        return match.group(1) if match else href.split("/")[-1].replace(".htm", "")

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        try:
            return parsedate_to_datetime(date_str).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            for fmt in ("%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
        return None
