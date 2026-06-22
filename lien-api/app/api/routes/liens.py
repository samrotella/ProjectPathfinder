"""Lien search and lookup endpoints.

All filters are optional and compose with AND. Free-text `q` matches across the
party, property, and legal-description fields. Results are paginated with a hard
cap on page size. Every query is parameterized via SQLAlchemy (no string
interpolation), so the search surface is not SQL-injectable.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.enums import DocumentType, LienStatus
from app.models import LienRecord
from app.schemas import LienOut, LienSearchResponse
from app.security import require_api_key

router = APIRouter(prefix="/v1", tags=["liens"], dependencies=[Depends(require_api_key)])
settings = get_settings()


def _apply_filters(stmt, *, q, claimant, owner, parcel_id, source, state,
                   document_type, status, recorded_from, recorded_to,
                   min_amount, max_amount):
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                LienRecord.claimant_name.ilike(like),
                LienRecord.owner_name.ilike(like),
                LienRecord.property_address.ilike(like),
                LienRecord.legal_description.ilike(like),
            )
        )
    if claimant:
        stmt = stmt.where(LienRecord.claimant_name.ilike(f"%{claimant}%"))
    if owner:
        stmt = stmt.where(LienRecord.owner_name.ilike(f"%{owner}%"))
    if parcel_id:
        stmt = stmt.where(LienRecord.parcel_id == parcel_id)
    if source:
        stmt = stmt.where(LienRecord.source_id == source)
    if state:
        stmt = stmt.where(LienRecord.state == state.upper())
    if document_type:
        stmt = stmt.where(LienRecord.document_type == document_type)
    if status:
        stmt = stmt.where(LienRecord.status == status)
    if recorded_from:
        stmt = stmt.where(LienRecord.recording_date >= recorded_from)
    if recorded_to:
        stmt = stmt.where(LienRecord.recording_date <= recorded_to)
    if min_amount is not None:
        stmt = stmt.where(LienRecord.amount_claimed >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(LienRecord.amount_claimed <= max_amount)
    return stmt


@router.get("/liens", response_model=LienSearchResponse)
async def search_liens(
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(None, description="Free text across parties, address, legal description."),
    claimant: str | None = Query(None, description="Claimant (lienor) name contains."),
    owner: str | None = Query(None, description="Property owner name contains."),
    parcel_id: str | None = Query(None, description="Exact parcel / APN / folio."),
    source: str | None = Query(None, description="Source id, e.g. miami-dade-fl or maricopa-az."),
    state: str | None = Query(None, min_length=2, max_length=2, description="Two-letter state."),
    document_type: DocumentType | None = Query(None),
    status: LienStatus | None = Query(None),
    recorded_from: date | None = Query(None, description="Recording date >= (ISO date)."),
    recorded_to: date | None = Query(None, description="Recording date <= (ISO date)."),
    min_amount: Decimal | None = Query(None, ge=0),
    max_amount: Decimal | None = Query(None, ge=0),
    limit: int = Query(25, ge=1),
    offset: int = Query(0, ge=0),
) -> LienSearchResponse:
    limit = min(limit, settings.max_page_size)
    filters = dict(
        q=q, claimant=claimant, owner=owner, parcel_id=parcel_id, source=source,
        state=state, document_type=document_type, status=status,
        recorded_from=recorded_from, recorded_to=recorded_to,
        min_amount=min_amount, max_amount=max_amount,
    )

    count_stmt = _apply_filters(select(func.count(LienRecord.id)), **filters)
    total = await session.scalar(count_stmt) or 0

    stmt = _apply_filters(select(LienRecord), **filters)
    stmt = stmt.order_by(LienRecord.recording_date.desc().nullslast()).limit(limit).offset(offset)
    rows = (await session.scalars(stmt)).all()

    return LienSearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=[LienOut.model_validate(r) for r in rows],
    )


@router.get("/liens/{lien_id}", response_model=LienOut)
async def get_lien(lien_id: str, session: AsyncSession = Depends(get_session)) -> LienOut:
    row = await session.get(LienRecord, lien_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Lien not found.")
    return LienOut.model_validate(row)
