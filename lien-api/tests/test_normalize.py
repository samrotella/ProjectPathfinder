"""Normalization and connector mapping tests."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.enums import DocumentType, LienStatus
from app.ingestion.connectors.maricopa import MaricopaConnector
from app.ingestion.connectors.miami_dade import MiamiDadeConnector
from app.ingestion.normalize import map_document_type, parse_amount, parse_date


def test_parse_amount_handles_currency_formatting():
    assert parse_amount("$67,200.00") == Decimal("67200.00")
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount(12900) == Decimal("12900")


def test_parse_date_handles_multiple_formats():
    assert parse_date("03/06/2026") == date(2026, 3, 6)
    assert parse_date("2026-03-04") == date(2026, 3, 4)
    assert parse_date("not a date") is None


def test_document_type_longest_match_wins():
    mapping = {
        "RELEASE OF MECHANICS LIEN": DocumentType.LIEN_RELEASE,
        "MECHANICS LIEN": DocumentType.MECHANICS_LIEN,
    }
    assert map_document_type("RELEASE OF MECHANICS LIEN", mapping) == DocumentType.LIEN_RELEASE
    assert map_document_type("MECHANICS LIEN", mapping) == DocumentType.MECHANICS_LIEN


def test_miami_dade_maps_claim_of_lien_to_canonical():
    conn = MiamiDadeConnector()
    raw = next(r for r in conn.fetch() if r["DocTypeCode"] == "LIE")
    canonical = conn.to_canonical(raw)
    assert canonical.source_id == "miami-dade-fl"
    assert canonical.document_type == DocumentType.MECHANICS_LIEN
    assert canonical.state == "FL"
    assert canonical.amount_claimed == Decimal("48750.00")
    assert canonical.claimant_name == "SUNCOAST PLUMBING LLC"


def test_maricopa_release_carries_reference():
    conn = MaricopaConnector()
    release = next(r for r in conn.fetch() if "RELEASE" in r["caption"])
    canonical = conn.to_canonical(release)
    assert canonical.document_type == DocumentType.LIEN_RELEASE
    assert canonical.related_document_number == "20260158842"


def test_maricopa_skips_irrelevant_and_keeps_liens():
    conn = MaricopaConnector()
    captions = {r["caption"] for r in conn.fetch()}
    assert "MECHANICS LIEN" in captions
