"""Canonical vocabularies shared by the ORM, schemas, and connectors.

Every source's raw document-type strings get mapped into DocumentType, and every
record carries a normalized LienStatus. Keeping these in one place is what lets
the API present a single coherent model across very different jurisdictions.
"""
from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    MECHANICS_LIEN = "mechanics_lien"
    LIEN_RELEASE = "lien_release"          # release / satisfaction of a prior lien
    NOTICE_OF_COMPLETION = "notice_of_completion"
    PRELIMINARY_NOTICE = "preliminary_notice"  # e.g. AZ 20-day preliminary notice
    LIS_PENDENS = "lis_pendens"
    OTHER = "other"


class LienStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    UNKNOWN = "unknown"
