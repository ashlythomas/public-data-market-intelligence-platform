"""Document normalization service."""

import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup

PARSER_VERSION = "0.1.0"


def detect_language(text: str) -> str:
    """Simple language detection heuristic for MVP."""
    if not text:
        return "unknown"
    # Check for common non-English patterns
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    return "en"


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def extract_html(content: bytes | str) -> tuple[str, str | None]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(content, "lxml")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = None
    title_tag = soup.find("title") or soup.find("h1")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Try to find main content
    main = (
        soup.find("div", id="article")
        or soup.find("div", class_="col-xs-12 col-sm-8 col-md-8")
        or soup.find("article")
        or soup.find("main")
        or soup.find("div", class_="content")
        or soup.body
    )
    if main:
        body = main.get_text(separator="\n", strip=True)
    else:
        body = soup.get_text(separator="\n", strip=True)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return normalize_unicode(body), title


def extract_json(content: bytes | str) -> tuple[str, str | None]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    data = json.loads(content)
    title = data.get("title") or data.get("name")
    body = data.get("body") or data.get("content") or data.get("text") or json.dumps(data, indent=2)
    return normalize_unicode(str(body)), title


def extract_text(content: bytes | str) -> tuple[str, str | None]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return normalize_unicode(content.strip()), None


def parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).replace(tzinfo=UTC)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%B %d, %Y"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def normalize_document(
    *,
    raw_envelope: dict[str, Any],
    content: bytes,
) -> dict[str, Any] | None:
    content_type = raw_envelope.get("content_type", "text/plain")
    source_url = raw_envelope["source_url"]
    source_id = raw_envelope["source_id"]

    if "html" in content_type:
        body, title = extract_html(content)
    elif "json" in content_type:
        body, title = extract_json(content)
    else:
        body, title = extract_text(content)

    if not body or len(body.strip()) < 50:
        return None

    metadata = raw_envelope.get("metadata", {})
    title = title or metadata.get("title")
    published_at = parse_published_at(raw_envelope.get("published_at")) or parse_published_at(
        metadata.get("published_at")
    )

    document_id = uuid.uuid4()
    return {
        "document_id": str(document_id),
        "source_id": source_id,
        "external_id": raw_envelope.get("external_id"),
        "canonical_url": source_url,
        "title": title,
        "body": body,
        "summary": body[:500] if len(body) > 500 else None,
        "authors": metadata.get("authors", []),
        "language": detect_language(body),
        "published_at": published_at.isoformat() if published_at else None,
        "retrieved_at": raw_envelope.get("retrieved_at", datetime.now(UTC).isoformat()),
        "document_type": "press_release" if source_id == "fed" else "article",
        "country_codes": ["US"] if source_id == "fed" else [],
        "topic_labels": [],
        "content_hash": raw_envelope["content_hash"],
        "parser_version": PARSER_VERSION,
        "source_record_id": source_id,
    }
