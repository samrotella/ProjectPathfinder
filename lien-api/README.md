# Lien API

A modern, normalized API for mechanic's lien records, built to ingest from many
jurisdictions and serve them through one consistent search interface. This MVP
ships with two live-shaped connectors — **Miami-Dade County, FL** (a daily
feed) and **Maricopa County, AZ** (a bulk export) — chosen because their access
patterns are deliberately different, which forces the canonical model to
generalize from day one.

## Stack

Python 3.11+ · FastAPI · async SQLAlchemy 2.0 · Pydantic v2 · PostgreSQL
(production) / SQLite (local dev, zero infra).

## Quickstart (no infrastructure required)

```bash
pip install -e ".[dev]"        # or: pip install fastapi uvicorn[standard] sqlalchemy pydantic pydantic-settings aiosqlite python-dateutil httpx pytest pytest-asyncio
cp .env.example .env

python -m scripts.seed         # ingest the bundled sample data into SQLite
uvicorn app.main:app --reload  # serve on http://127.0.0.1:8000
```

Then:

```bash
# Interactive docs (auto-generated OpenAPI):
open http://127.0.0.1:8000/docs

# Search (note the API key header):
curl -H "X-API-Key: dev-key-123" \
  "http://127.0.0.1:8000/v1/liens?document_type=mechanics_lien&status=active"

curl -H "X-API-Key: dev-key-123" \
  "http://127.0.0.1:8000/v1/liens?q=plumbing&state=FL"
```

Run the tests:

```bash
pytest
```

## Architecture

```
            ┌──────────────┐   ┌──────────────┐
  sources → │ MiamiDade    │   │ Maricopa     │   (one connector per jurisdiction)
            │ connector    │   │ connector    │
            └──────┬───────┘   └──────┬───────┘
                   │  fetch() raw     │  fetch() raw
                   ▼                  ▼
            ┌─────────────────────────────────┐
            │ normalize → CanonicalLienInput  │  (shared date/money/name/doc-type logic)
            └────────────────┬────────────────┘
                             ▼
            ┌─────────────────────────────────┐
            │ pipeline: idempotent upsert      │  (natural key: source_id + source_record_id)
            │          + release→lien linking  │
            └────────────────┬────────────────┘
                             ▼
                     PostgreSQL (lien_records)
                             ▲
                             │  parameterized queries
            ┌────────────────┴────────────────┐
            │ FastAPI: /v1/liens search+lookup │  (API key auth, rate limit, paging)
            └─────────────────────────────────┘
```

The **canonical lien record** (`app/models.py`, `app/schemas.py`) is the center
of the design. Every connector maps its source-specific shape into it, so all
querying, paging, and serving is jurisdiction-agnostic. Adding a new county is
one connector class plus one line in `app/ingestion/registry.py`.

Ingestion runs as a **separate process** from the API (`python -m scripts.seed`,
or a scheduled job in production), so ingestion load never affects query latency.

## Connecting real data

Both connectors read a bundled JSON fixture by default so the pipeline runs
offline. Each accepts a `data_path` pointing at a real downloaded file with the
same field shape — no other code changes:

- **Miami-Dade**: register for the Clerk's Commercial Data Services (FTP bulk
  files + API for Official Records). Official-records access does not require the
  notarized form that court records do.
- **Maricopa**: purchase the Recorder's bulk index + image export. The AZ caption
  requirement gives a clean document-type field to filter on.

See `CLAUDE.md` for the field-by-field reality (notably: claim **amounts** often
live in the document image, not the index — OCR is the real work) and the
prioritized production roadmap.

## Endpoints

| Method | Path             | Auth | Purpose                         |
|--------|------------------|------|---------------------------------|
| GET    | `/health`        | no   | Liveness                        |
| GET    | `/ready`         | no   | Readiness (checks DB)           |
| GET    | `/v1/liens`      | yes  | Search/filter (paginated)       |
| GET    | `/v1/liens/{id}` | yes  | Single record by id             |

`/v1/liens` filters: `q`, `claimant`, `owner`, `parcel_id`, `source`, `state`,
`document_type`, `status`, `recorded_from`, `recorded_to`, `min_amount`,
`max_amount`, `limit`, `offset`.

## A note on the data

These records are public, but they contain personal names and addresses, and
lien law is highly jurisdiction-specific. Confirm redistribution terms for each
source before going to production. This is engineering guidance, not legal advice.
