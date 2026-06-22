"""Miami-Dade County, FL connector — FEED access pattern.

Real source: the Clerk of Court's Commercial Data Services exposes Official
Records as bulk files over FTP and via an API, refreshed daily/weekly. The
production `fetch` would pull the latest official-records delta file (or page
the API) for `since`, authenticating with credentials from the environment.

For the MVP, `fetch` reads a bundled sample file with the same field shape so the
full pipeline runs offline. Point `data_path` at a real downloaded feed file to
ingest live data without changing any other code.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from app.enums import DocumentType
from app.ingestion.base import RawRecord, SourceConnector
from app.ingestion.normalize import (
    clean_name,
    map_document_type,
    parse_amount,
    parse_date,
)
from app.schemas import CanonicalLienInput

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "miami_dade_sample.json"

# Map the source's DocType text to canonical types. Longest match wins.
_DOC_TYPE_MAP = {
    "SATISFACTION OF CLAIM OF LIEN": DocumentType.LIEN_RELEASE,
    "RELEASE OF LIEN": DocumentType.LIEN_RELEASE,
    "CLAIM OF LIEN": DocumentType.MECHANICS_LIEN,
    "LIS PENDENS": DocumentType.LIS_PENDENS,
}

# Only these source doc types are liens or lien-adjacent; everything else is skipped.
_RELEVANT_DOC_CODES = {"LIE", "SAT", "LIS"}


class MiamiDadeConnector(SourceConnector):
    source_id = "miami-dade-fl"
    jurisdiction = "Miami-Dade County, FL"
    county = "Miami-Dade"
    state = "FL"

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or _FIXTURE

    def fetch(self, since: date | None = None) -> Iterable[RawRecord]:
        records = json.loads(self.data_path.read_text())
        for rec in records:
            if rec.get("DocTypeCode") not in _RELEVANT_DOC_CODES:
                continue
            if since:
                rd = parse_date(rec.get("RecordDate"))
                if rd and rd < since:
                    continue
            yield rec

    def to_canonical(self, raw: RawRecord) -> CanonicalLienInput:
        doc_type = map_document_type(raw.get("DocType"), _DOC_TYPE_MAP)
        # Consideration approximates the claim amount for claims of lien; for a
        # precise figure you'd OCR the document image (see CLAUDE.md).
        amount = parse_amount(raw.get("Consideration")) if doc_type == DocumentType.MECHANICS_LIEN else None
        return CanonicalLienInput(
            source_id=self.source_id,
            source_record_id=str(raw["CFN"]),
            source_url=f"https://onlineservices.miamidadeclerk.gov/officialrecords/CFNDetailsbyDocNum.aspx?QS={raw['CFN']}",
            document_number=str(raw["CFN"]),
            recording_date=parse_date(raw.get("RecordDate")),
            document_type=doc_type,
            raw_document_type=raw.get("DocType"),
            book=raw.get("Book"),
            page=raw.get("Page"),
            claimant_name=clean_name(raw.get("FirstPartyName")),
            owner_name=clean_name(raw.get("SecondPartyName")),
            property_address=raw.get("PropertyAddress"),
            parcel_id=raw.get("Folio"),
            legal_description=raw.get("LegalDescription"),
            amount_claimed=amount,
            related_document_number=raw.get("ReferenceCFN"),
            jurisdiction=self.jurisdiction,
            county=self.county,
            state=self.state,
            raw=raw,
        )
