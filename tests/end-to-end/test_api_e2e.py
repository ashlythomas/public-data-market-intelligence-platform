"""End-to-end test scenarios (requires running services)."""

import os

import httpx
import pytest

API_URL = os.environ.get("API_URL", "http://localhost:8000")


@pytest.fixture
def api_client():
    return httpx.Client(base_url=API_URL, timeout=30.0)


@pytest.mark.e2e
def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.e2e
def test_ready_endpoint(api_client):
    response = api_client.get("/ready")
    assert response.status_code == 200


@pytest.mark.e2e
def test_search_endpoint(api_client):
    response = api_client.post(
        "/v1/search",
        json={"query": "Federal Reserve inflation", "page": 1, "page_size": 10},
    )
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert "query_time_ms" in data


@pytest.mark.e2e
def test_documents_list(api_client):
    response = api_client.get("/v1/documents")
    if response.status_code == 200:
        data = response.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.e2e
def test_signals_list(api_client):
    response = api_client.get("/v1/signals")
    if response.status_code == 200:
        data = response.json()
        assert "items" in data
