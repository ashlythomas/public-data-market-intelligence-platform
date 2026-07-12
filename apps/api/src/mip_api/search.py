import time
from typing import Any

from mip_api.config import get_settings
from opensearchpy import AsyncOpenSearch

DOCUMENTS_INDEX = "documents-v1"
EVENTS_INDEX = "events-v1"
ENTITIES_INDEX = "entities-v1"
NARRATIVES_INDEX = "narratives-v1"

DOCUMENTS_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "document_id": {"type": "keyword"},
            "source_id": {"type": "keyword"},
            "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "body": {"type": "text"},
            "summary": {"type": "text"},
            "language": {"type": "keyword"},
            "published_at": {"type": "date"},
            "retrieved_at": {"type": "date"},
            "document_type": {"type": "keyword"},
            "country_codes": {"type": "keyword"},
            "topic_labels": {"type": "keyword"},
            "content_hash": {"type": "keyword"},
        }
    },
}


class SearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenSearch(
            hosts=[settings.opensearch_url],
            use_ssl=False,
            verify_certs=False,
        )

    async def ensure_indices(self) -> None:
        for index, mapping in [
            (DOCUMENTS_INDEX, DOCUMENTS_MAPPING),
            (EVENTS_INDEX, DOCUMENTS_MAPPING),
            (ENTITIES_INDEX, DOCUMENTS_MAPPING),
            (NARRATIVES_INDEX, DOCUMENTS_MAPPING),
        ]:
            if not await self.client.indices.exists(index=index):
                await self.client.indices.create(index=index, body=mapping)

    async def index_document(self, doc: dict[str, Any]) -> None:
        await self.client.index(
            index=DOCUMENTS_INDEX,
            id=doc["document_id"],
            body=doc,
            refresh=True,
        )

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, float]:
        start = time.monotonic()
        filters = filters or {}

        must_clauses: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "body", "summary", "topic_labels"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses: list[dict[str, Any]] = []
        if filters.get("source_id"):
            filter_clauses.append({"term": {"source_id": filters["source_id"]}})
        if filters.get("language"):
            filter_clauses.append({"term": {"language": filters["language"]}})
        if filters.get("country"):
            filter_clauses.append({"term": {"country_codes": filters["country"]}})
        if filters.get("topic"):
            filter_clauses.append({"term": {"topic_labels": filters["topic"]}})
        if filters.get("date_from") or filters.get("date_to"):
            date_range: dict[str, str] = {}
            if filters.get("date_from"):
                date_range["gte"] = filters["date_from"]
            if filters.get("date_to"):
                date_range["lte"] = filters["date_to"]
            filter_clauses.append({"range": {"published_at": date_range}})

        body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "from": (page - 1) * page_size,
            "size": page_size,
            "highlight": {
                "fields": {
                    "body": {"fragment_size": 200, "number_of_fragments": 1},
                    "title": {},
                }
            },
        }

        response = await self.client.search(index=DOCUMENTS_INDEX, body=body)
        elapsed_ms = (time.monotonic() - start) * 1000

        hits = response["hits"]["hits"]
        total = response["hits"]["total"]["value"]
        results = []
        for hit in hits:
            source = hit["_source"]
            snippet = None
            if "highlight" in hit:
                highlights = hit["highlight"]
                snippet = highlights.get("body", highlights.get("title", [None]))[0]
            results.append(
                {
                    "id": source.get("document_id", hit["_id"]),
                    "type": "document",
                    "title": source.get("title"),
                    "snippet": snippet or source.get("summary", "")[:200],
                    "score": hit["_score"],
                    "source_id": source.get("source_id"),
                    "published_at": source.get("published_at"),
                    "provenance": {
                        "source_id": source.get("source_id"),
                        "document_id": source.get("document_id"),
                        "content_hash": source.get("content_hash"),
                    },
                }
            )
        return results, total, elapsed_ms

    async def close(self) -> None:
        await self.client.close()
