import asyncio
import time
from typing import Any

from mip_api.config import get_settings
from opensearchpy import OpenSearch

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


def _reciprocal_rank_fusion(
    keyword_results: list[dict[str, Any]],
    semantic_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    for rank, item in enumerate(keyword_results):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        items[doc_id] = item
    for rank, item in enumerate(semantic_results):
        doc_id = item["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        items[doc_id] = item
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{**items[doc_id], "score": score} for doc_id, score in ranked]


class SearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self._url = settings.opensearch_url
        self.client = OpenSearch(hosts=[self._url], use_ssl=False, verify_certs=False)

    async def ensure_indices(self) -> None:
        await asyncio.to_thread(self._ensure_indices_sync)

    def _ensure_indices_sync(self) -> None:
        for index, mapping in [
            (DOCUMENTS_INDEX, DOCUMENTS_MAPPING),
            (EVENTS_INDEX, DOCUMENTS_MAPPING),
            (ENTITIES_INDEX, DOCUMENTS_MAPPING),
            (NARRATIVES_INDEX, DOCUMENTS_MAPPING),
        ]:
            if not self.client.indices.exists(index=index):
                self.client.indices.create(index=index, body=mapping)

    async def index_document(self, doc: dict[str, Any]) -> None:
        await asyncio.to_thread(
            self.client.index,
            index=DOCUMENTS_INDEX,
            id=doc["document_id"],
            body=doc,
            refresh=True,
        )

    def _keyword_search(
        self,
        query: str,
        *,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        index: str = DOCUMENTS_INDEX,
        result_type: str = "document",
    ) -> tuple[list[dict[str, Any]], int]:
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

        body: dict[str, Any] = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "from": (page - 1) * page_size,
            "size": page_size,
            "highlight": {
                "fields": {
                    "body": {"fragment_size": 200, "number_of_fragments": 1},
                    "title": {},
                }
            },
        }
        response = self.client.search(index=index, body=body)
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
                    "type": result_type,
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
        return results, total

    def _semantic_search(self, query: str, page_size: int) -> list[dict[str, Any]]:
        """Semantic search via more_like_this as MVP vector proxy."""
        body = {
            "query": {
                "more_like_this": {
                    "fields": ["body", "title"],
                    "like": query,
                    "min_term_freq": 1,
                }
            },
            "size": page_size,
        }
        try:
            response = self.client.search(index=DOCUMENTS_INDEX, body=body)
        except Exception:
            return []
        return [
            {
                "id": hit["_source"].get("document_id", hit["_id"]),
                "type": "document",
                "title": hit["_source"].get("title"),
                "snippet": hit["_source"].get("summary", "")[:200],
                "score": hit["_score"],
                "source_id": hit["_source"].get("source_id"),
                "published_at": hit["_source"].get("published_at"),
                "provenance": {"document_id": hit["_source"].get("document_id")},
            }
            for hit in response["hits"]["hits"]
        ]

    async def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        hybrid: bool = True,
    ) -> tuple[list[dict[str, Any]], int, float]:
        start = time.monotonic()
        filters = filters or {}
        fetch_size = page * page_size

        if hybrid:
            keyword_results, doc_total = await asyncio.to_thread(
                self._keyword_search,
                query,
                filters=filters,
                page=1,
                page_size=fetch_size,
                index=DOCUMENTS_INDEX,
                result_type="document",
            )
            semantic_results = await asyncio.to_thread(self._semantic_search, query, fetch_size)
            fused_docs = _reciprocal_rank_fusion(keyword_results, semantic_results)
            event_results, event_total = await asyncio.to_thread(
                self._keyword_search,
                query,
                filters=filters,
                page=1,
                page_size=fetch_size,
                index=EVENTS_INDEX,
                result_type="event",
            )
            narrative_results, narrative_total = await asyncio.to_thread(
                self._keyword_search,
                query,
                filters=filters,
                page=1,
                page_size=fetch_size,
                index=NARRATIVES_INDEX,
                result_type="narrative",
            )
            combined = sorted(
                [*fused_docs, *event_results, *narrative_results],
                key=lambda item: float(item.get("score", 0.0)),
                reverse=True,
            )
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            elapsed_ms = (time.monotonic() - start) * 1000
            return combined[start_index:end_index], doc_total + event_total + narrative_total, elapsed_ms

        doc_results, doc_total = await asyncio.to_thread(
            self._keyword_search,
            query,
            filters=filters,
            page=1,
            page_size=fetch_size,
            index=DOCUMENTS_INDEX,
            result_type="document",
        )
        event_results, event_total = await asyncio.to_thread(
            self._keyword_search,
            query,
            filters=filters,
            page=1,
            page_size=fetch_size,
            index=EVENTS_INDEX,
            result_type="event",
        )
        narrative_results, narrative_total = await asyncio.to_thread(
            self._keyword_search,
            query,
            filters=filters,
            page=1,
            page_size=fetch_size,
            index=NARRATIVES_INDEX,
            result_type="narrative",
        )
        combined = sorted(
            [*doc_results, *event_results, *narrative_results],
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        elapsed_ms = (time.monotonic() - start) * 1000
        return combined[start_index:end_index], doc_total + event_total + narrative_total, elapsed_ms

    async def close(self) -> None:
        pass
