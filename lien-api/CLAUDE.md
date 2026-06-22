# CLAUDE.md

Standing instructions and context for working on this codebase with Claude Code.
Read this before making changes.

## What this is

A normalized API for mechanic's lien records. It ingests from per-jurisdiction
connectors, maps everything into one canonical schema, stores it in Postgres, and
serves search/lookup over HTTP. This is a **data product**: the API is the easy
part; the connectors, normalization, and (eventually) OCR are where the real work
and the real value live.

## Stack and conventions

- Python 3.11+, FastAPI, async SQLAlchemy 2.0, Pydantic v2, Postgres (prod) /
  SQLite (dev).
- Everything is async end to end. Don't introduce blocking DB or HTTP calls in
  request or pipeline paths; use `httpx.AsyncClient` and the async session.
- The public API contract (`LienOut`, `LienSearchResponse` in `app/schemas.py`)
  is decoupled from the ORM (`app/models.py`). Change storage freely; treat the
  response models as a stable contract and version breaking changes under a new
  `/vN` prefix.
- Canonical vocabularies live in `app/enums.py`. New document types or statuses
  go there first, then into connector mappings.
- Tests must pass (`pytest`) before any change is considered done. Add a test
  with every connector or normalization change.

## Architectural rules

1. **One connector per jurisdiction.** Implement `SourceConnector` in
   `app/ingestion/connectors/`, register it in `registry.py`. Connectors own
   their access pattern (feed vs bulk vs scrape) and their raw→canonical mapping.
   Nothing downstream may branch on `source_id`.
2. **Idempotent ingestion.** Upserts key on `(source_id, source_record_id)`.
   Re-running a feed must never duplicate rows.
3. **Provenance is preserved.** The original record is stored in `raw` so fields
   can be re-derived later (e.g. when OCR improves) without re-fetching.
4. **Ingestion is decoupled from serving.** Keep the pipeline runnable as its own
   process so it can scale and fail independently of the API.

## The data reality (important)

The county index gives you structured fields — party names, document type,
recording date, book/page, parcel, legal description. But the **claim amount and
other lien specifics frequently exist only inside the recorded document image**,
not the index. The connectors currently approximate `amount_claimed` from the
index's consideration/amount field; treat that as provisional. A real OCR +
parsing stage (see roadmap) is required for trustworthy amounts.

Other per-source notes:
- **Maricopa (AZ)**: claimant is the grantor, owner the grantee — a simplification
  that won't hold for every document type; revisit when adding more captions.
- **Miami-Dade (FL)**: party roles come from the feed; map them explicitly rather
  than assuming first-party = claimant for every doc type.
- Entity resolution across sources (same claimant/property in different counties)
  is not yet implemented.

## Production roadmap (in priority order)

1. **Migrations**: replace `init_db()` table creation with Alembic. `init_db`
   exists only for dev convenience and is skipped when `ENVIRONMENT != development`.
2. **Postgres-native search**: add a `tsvector` column + GIN index for `q`, and
   `pg_trgm` for fuzzy name matching. The current `ILIKE` works everywhere but
   won't scale; keep the same query params so the contract is unchanged.
3. **OCR/parse stage**: pull document images, extract claim amount and other
   in-document fields, write back to the canonical record (keep `raw` as source
   of truth). This is the highest-value data improvement.
4. **AuthN/Z**: move from static API keys to OAuth2 client-credentials / JWT with
   scopes and per-client quotas. `require_api_key` in `app/security.py` is the
   single seam to replace.
5. **Distributed rate limiting**: the in-process limiter only protects one node.
   Back it with Redis (or an API gateway) for multi-node deployments.
6. **Ingestion at scale**: move from the seed script to a scheduled worker / task
   queue (Arq or Celery) with per-source incremental `since` cursors and retries.
7. **Observability**: structured logging, request IDs, OpenTelemetry traces, and
   an audit log of who queried what (relevant given the PII in these records).
8. **Compliance**: confirm per-source redistribution terms; add redaction hooks
   for any exempt fields; document data retention.

## Where things are

- `app/config.py` — settings (env-driven)
- `app/models.py` / `app/schemas.py` — canonical record (ORM / API)
- `app/enums.py` — document types and statuses
- `app/ingestion/base.py` — the `SourceConnector` contract
- `app/ingestion/normalize.py` — shared parsing/mapping helpers
- `app/ingestion/connectors/` — one file per jurisdiction
- `app/ingestion/pipeline.py` — upsert + release linking
- `app/api/routes/liens.py` — search/lookup
- `app/security.py` — auth + rate limiting (the seam for #4 and #5)
- `scripts/seed.py` — run the pipeline against fixtures
- `tests/` — normalization + end-to-end API tests
