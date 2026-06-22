"""ORM model for the canonical lien record.

The canonical record is the heart of the system: every connector maps its
source-specific shape into this one structure. `source_id` + `source_record_id`
is the natural key used for idempotent upserts, so re-running ingestion never
creates duplicates.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Date,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import DocumentType, LienStatus


def _uuid() -> str:
    return str(uuid.uuid4())


class LienRecord(Base):
    __tablename__ = "lien_records"
    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_source_record"),
        Index("ix_lien_claimant", "claimant_name"),
        Index("ix_lien_owner", "owner_name"),
        Index("ix_lien_parcel", "parcel_id"),
        Index("ix_lien_recording_date", "recording_date"),
        Index("ix_lien_doc_type", "document_type"),
        Index("ix_lien_jurisdiction", "jurisdiction"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Provenance / natural key
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024))

    # Recording metadata
    document_number: Mapped[str | None] = mapped_column(String(128))
    recording_date: Mapped[date | None] = mapped_column(Date)
    document_type: Mapped[DocumentType] = mapped_column(String(32), default=DocumentType.OTHER)
    raw_document_type: Mapped[str | None] = mapped_column(String(256))
    book: Mapped[str | None] = mapped_column(String(32))
    page: Mapped[str | None] = mapped_column(String(32))

    # Parties
    claimant_name: Mapped[str | None] = mapped_column(String(512))
    claimant_address: Mapped[str | None] = mapped_column(String(512))
    owner_name: Mapped[str | None] = mapped_column(String(512))

    # Property
    property_address: Mapped[str | None] = mapped_column(String(512))
    parcel_id: Mapped[str | None] = mapped_column(String(64))
    legal_description: Mapped[str | None] = mapped_column(String(2048))

    # Claim
    amount_claimed: Mapped[float | None] = mapped_column(Numeric(14, 2))
    status: Mapped[LienStatus] = mapped_column(String(16), default=LienStatus.UNKNOWN)
    related_document_number: Mapped[str | None] = mapped_column(String(128))

    # Jurisdiction
    jurisdiction: Mapped[str] = mapped_column(String(128), nullable=False)
    county: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(2))

    # Original payload for audit/provenance and future re-parsing.
    raw: Mapped[dict | None] = mapped_column(JSON)

    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
