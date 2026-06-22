"""Shared normalization helpers.

Connectors differ in their raw shapes, but date parsing, money parsing, name
cleanup, and document-type mapping are common concerns. Centralizing them keeps
connectors thin and keeps normalization behavior consistent and testable.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from dateutil import parser as date_parser

from app.enums import DocumentType

_WHITESPACE = re.compile(r"\s+")
_MONEY_STRIP = re.compile(r"[^0-9.\-]")


def clean_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WHITESPACE.sub(" ", value).strip().upper()
    return cleaned or None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date_parser.parse(str(value)).date()
    except (ValueError, OverflowError, TypeError):
        return None


def parse_amount(value: str | int | float | None) -> Decimal | None:
    """Parse a monetary value. Lien claim amounts often arrive as '$12,500.00'
    or are absent (the figure lives inside the document image, not the index)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    stripped = _MONEY_STRIP.sub("", str(value))
    if not stripped or stripped in {"-", "."}:
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None


def map_document_type(raw_type: str | None, mapping: dict[str, DocumentType]) -> DocumentType:
    """Map a source-specific document-type string to the canonical enum.

    `mapping` keys are matched case-insensitively as substrings, longest first,
    so 'RELEASE OF MECHANICS LIEN' resolves to LIEN_RELEASE rather than
    MECHANICS_LIEN.
    """
    if not raw_type:
        return DocumentType.OTHER
    haystack = raw_type.upper()
    for key in sorted(mapping, key=len, reverse=True):
        if key.upper() in haystack:
            return mapping[key]
    return DocumentType.OTHER


def now() -> datetime:
    return datetime.utcnow()
