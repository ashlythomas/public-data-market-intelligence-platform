"""Unit tests for connector runner replay behavior."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from mip_connector_fed.base import RawPayload, SourceItem
from mip_connector_fed.shared_runner import run_connector
from mip_database.models import RawDocument


class _FakeExecuteResult:
    def scalar_one_or_none(self):  # noqa: D401 - test helper
        return None


class _FakeSession:
    def __init__(
        self, *, existing_raw: RawDocument | None = None, run_obj: object | None = None
    ) -> None:
        self._existing_raw = existing_raw
        self._run_obj = run_obj

    async def execute(self, _query):
        return _FakeExecuteResult()

    def add(self, _obj):
        return None

    async def commit(self):
        return None

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "RawDocument":
            return self._existing_raw
        if model_name == "IngestionRun":
            return self._run_obj
        return None


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *_args):
        return None


class _FakeSessionFactory:
    def __init__(self, sessions: list[_FakeSession]) -> None:
        self._sessions = iter(sessions)

    def __call__(self):
        return _FakeSessionContext(next(self._sessions))


class _FakeProducer:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published: list[tuple[str, dict]] = []

    async def start(self):
        return None

    async def stop(self):
        return None

    async def publish(self, topic: str, message: dict):
        if self.should_fail:
            raise RuntimeError("publish failed")
        self.published.append((topic, message))


class _FakeConnector:
    connector_name = "fake"
    connector_version = "0.1.0"

    def __init__(self, item: SourceItem, payload: RawPayload) -> None:
        self._item = item
        self._payload = payload
        self.processed_urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def load_checkpoint(self, _checkpoint):
        return None

    async def discover(self, _checkpoint):
        yield self._item

    async def fetch_with_retry(self, _item):
        return self._payload

    def content_hash(self, _content: bytes) -> str:
        return "payload-hash"

    def mark_processed(self, item: SourceItem) -> None:
        self.processed_urls.append(item.url)

    async def checkpoint(self):
        return {"seen_urls": self.processed_urls}


@pytest.mark.asyncio
async def test_duplicate_record_is_republished_and_marked_processed(monkeypatch):
    item = SourceItem(external_id="ext-1", url="https://example.com/doc/1")
    payload = RawPayload(
        content=b"body",
        content_type="text/html",
        source_url=item.url,
        external_id=item.external_id,
        published_at=None,
        metadata={"title": "x"},
    )
    ingestion_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "fed:ext-1:payload-hash",
    )
    existing = RawDocument(
        ingestion_id=ingestion_id,
        source_id="fed",
        external_id="ext-1",
        source_url=item.url,
        retrieved_at=datetime.now(UTC),
        published_at=None,
        content_type="text/html",
        object_store_uri="s3://bucket/raw/1",
        content_hash="payload-hash",
        connector_version="0.1.0",
        metadata_={"title": "x"},
    )

    run_obj = SimpleNamespace()
    session_factory = _FakeSessionFactory(
        [
            _FakeSession(),
            _FakeSession(existing_raw=existing),
            _FakeSession(run_obj=run_obj),
        ]
    )
    producer = _FakeProducer(should_fail=False)
    connector = _FakeConnector(item, payload)

    monkeypatch.setattr(
        "mip_connector_fed.shared_runner.get_settings",
        lambda: SimpleNamespace(
            s3_endpoint_url="http://localhost:9000",
            s3_access_key="x",
            s3_secret_key="y",
            s3_bucket_raw="raw",
            kafka_bootstrap_servers="localhost:9092",
        ),
    )
    monkeypatch.setattr("mip_connector_fed.shared_runner.async_session_factory", session_factory)
    monkeypatch.setattr("mip_connector_fed.shared_runner.KafkaProducer", lambda _servers: producer)
    monkeypatch.setattr("mip_connector_fed.shared_runner.ObjectStorage", lambda **_kwargs: object())

    result = await run_connector(
        connector,
        source_id="fed",
        kafka_topic="raw.central-bank.v1",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )

    assert result["items_failed"] == 0
    assert connector.processed_urls == [item.url]
    assert len(producer.published) == 1
    assert producer.published[0][0] == "raw.central-bank.v1"


@pytest.mark.asyncio
async def test_duplicate_record_publish_failure_is_not_marked_processed(monkeypatch):
    item = SourceItem(external_id="ext-1", url="https://example.com/doc/1")
    payload = RawPayload(
        content=b"body",
        content_type="text/html",
        source_url=item.url,
        external_id=item.external_id,
        published_at=None,
        metadata={"title": "x"},
    )
    ingestion_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "fed:ext-1:payload-hash",
    )
    existing = RawDocument(
        ingestion_id=ingestion_id,
        source_id="fed",
        external_id="ext-1",
        source_url=item.url,
        retrieved_at=datetime.now(UTC),
        published_at=None,
        content_type="text/html",
        object_store_uri="s3://bucket/raw/1",
        content_hash="payload-hash",
        connector_version="0.1.0",
        metadata_={"title": "x"},
    )

    run_obj = SimpleNamespace()
    session_factory = _FakeSessionFactory(
        [
            _FakeSession(),
            _FakeSession(existing_raw=existing),
            _FakeSession(run_obj=run_obj),
        ]
    )
    producer = _FakeProducer(should_fail=True)
    connector = _FakeConnector(item, payload)

    monkeypatch.setattr(
        "mip_connector_fed.shared_runner.get_settings",
        lambda: SimpleNamespace(
            s3_endpoint_url="http://localhost:9000",
            s3_access_key="x",
            s3_secret_key="y",
            s3_bucket_raw="raw",
            kafka_bootstrap_servers="localhost:9092",
        ),
    )
    monkeypatch.setattr("mip_connector_fed.shared_runner.async_session_factory", session_factory)
    monkeypatch.setattr("mip_connector_fed.shared_runner.KafkaProducer", lambda _servers: producer)
    monkeypatch.setattr("mip_connector_fed.shared_runner.ObjectStorage", lambda **_kwargs: object())

    result = await run_connector(
        connector,
        source_id="fed",
        kafka_topic="raw.central-bank.v1",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )

    assert result["items_failed"] == 1
    assert connector.processed_urls == []
