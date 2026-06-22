"""End-to-end API tests: ingest into an in-memory DB, then exercise the API."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import SessionLocal, init_db
from app.enums import DocumentType, LienStatus
from app.ingestion.pipeline import run_pipeline
from app.ingestion.registry import default_connectors
from app.main import app

HEADERS = {"X-API-Key": "dev-key-123"}


@pytest_asyncio.fixture
async def client():
    await init_db()
    async with SessionLocal() as session:
        await run_pipeline(session, default_connectors())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_is_open(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_search_requires_api_key(client):
    resp = await client.get("/v1/liens")
    assert resp.status_code == 401


async def test_search_returns_records(client):
    resp = await client.get("/v1/liens", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["results"]) >= 1


async def test_filter_by_document_type(client):
    resp = await client.get(
        "/v1/liens", headers=HEADERS, params={"document_type": DocumentType.MECHANICS_LIEN.value}
    )
    assert resp.status_code == 200
    for r in resp.json()["results"]:
        assert r["document_type"] == DocumentType.MECHANICS_LIEN.value


async def test_release_marks_referenced_lien_released(client):
    # The Maricopa release references lien 20260158842; it should be RELEASED.
    resp = await client.get(
        "/v1/liens", headers=HEADERS,
        params={"source": "maricopa-az", "document_type": DocumentType.MECHANICS_LIEN.value},
    )
    records = {r["source_record_id"]: r for r in resp.json()["results"]}
    assert records["20260158842"]["status"] == LienStatus.RELEASED.value
    # The other lien has no release and stays active.
    assert records["20260175329"]["status"] == LienStatus.ACTIVE.value


async def test_free_text_search(client):
    resp = await client.get("/v1/liens", headers=HEADERS, params={"q": "saguaro"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_cross_jurisdiction_in_one_query(client):
    resp = await client.get("/v1/liens", headers=HEADERS, params={"limit": 100})
    sources = {r["source_id"] for r in resp.json()["results"]}
    assert {"miami-dade-fl", "maricopa-az"}.issubset(sources)
