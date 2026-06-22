"""Ingestion orchestration.

For each connector: fetch raw records, normalize to canonical, and upsert by the
(source_id, source_record_id) natural key so re-runs are idempotent. A second
pass links releases to the liens they discharge and sets status accordingly.

This runs as a separate process from the API (cron, worker, or task queue) so
ingestion load never affects query latency — see CLAUDE.md for the scale path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DocumentType, LienStatus
from app.ingestion.base import SourceConnector
from app.models import LienRecord
from app.schemas import CanonicalLienInput


@dataclass
class IngestStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    releases_linked: int = 0
    by_source: dict[str, int] = field(default_factory=dict)


async def _upsert(session: AsyncSession, rec: CanonicalLienInput) -> str:
    """Insert or update one canonical record. Returns 'inserted' or 'updated'."""
    existing = await session.scalar(
        select(LienRecord).where(
            LienRecord.source_id == rec.source_id,
            LienRecord.source_record_id == rec.source_record_id,
        )
    )
    payload = rec.model_dump()
    # Default a fresh lien to ACTIVE; the release pass may override it later.
    if rec.document_type == DocumentType.MECHANICS_LIEN and rec.status == LienStatus.UNKNOWN:
        payload["status"] = LienStatus.ACTIVE

    if existing is None:
        session.add(LienRecord(**payload))
        return "inserted"

    for key, value in payload.items():
        setattr(existing, key, value)
    return "updated"


async def _link_releases(session: AsyncSession) -> int:
    """Set referenced liens to RELEASED for every release that names a prior doc."""
    linked = 0
    releases = await session.scalars(
        select(LienRecord).where(LienRecord.document_type == DocumentType.LIEN_RELEASE)
    )
    for rel in releases:
        if not rel.related_document_number:
            continue
        target = await session.scalar(
            select(LienRecord).where(
                LienRecord.source_id == rel.source_id,
                LienRecord.source_record_id == rel.related_document_number,
            )
        )
        if target and target.status != LienStatus.RELEASED:
            target.status = LienStatus.RELEASED
            linked += 1
    return linked


async def run_pipeline(
    session: AsyncSession,
    connectors: list[SourceConnector],
    since: date | None = None,
) -> IngestStats:
    stats = IngestStats()
    for connector in connectors:
        count = 0
        for raw in connector.fetch(since=since):
            canonical = connector.to_canonical(raw)
            result = await _upsert(session, canonical)
            setattr(stats, result, getattr(stats, result) + 1)
            count += 1
        stats.by_source[connector.source_id] = count
    await session.flush()
    stats.releases_linked = await _link_releases(session)
    await session.commit()
    return stats
