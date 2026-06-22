"""Pydantic schemas: the canonical ingestion input and the API I/O models.

`CanonicalLienInput` is what every connector must produce. `LienOut` is what the
API returns. Keeping them distinct means internal storage details can change
without breaking the public contract.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DocumentType, LienStatus


class CanonicalLienInput(BaseModel):
    """Normalized record emitted by a connector, ready to upsert."""

    source_id: str
    source_record_id: str
    source_url: str | None = None

    document_number: str | None = None
    recording_date: date | None = None
    document_type: DocumentType = DocumentType.OTHER
    raw_document_type: str | None = None
    book: str | None = None
    page: str | None = None

    claimant_name: str | None = None
    claimant_address: str | None = None
    owner_name: str | None = None

    property_address: str | None = None
    parcel_id: str | None = None
    legal_description: str | None = None

    amount_claimed: Decimal | None = None
    status: LienStatus = LienStatus.UNKNOWN
    related_document_number: str | None = None

    jurisdiction: str
    county: str | None = None
    state: str | None = None

    raw: dict | None = None


class LienOut(BaseModel):
    """Public representation of a lien record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    source_record_id: str
    source_url: str | None

    document_number: str | None
    recording_date: date | None
    document_type: DocumentType
    book: str | None
    page: str | None

    claimant_name: str | None
    owner_name: str | None
    property_address: str | None
    parcel_id: str | None
    legal_description: str | None

    amount_claimed: Decimal | None
    status: LienStatus
    related_document_number: str | None

    jurisdiction: str
    county: str | None
    state: str | None

    ingested_at: datetime
    updated_at: datetime


class LienSearchResponse(BaseModel):
    total: int = Field(description="Total records matching the filters (ignoring paging).")
    limit: int
    offset: int
    results: list[LienOut]
