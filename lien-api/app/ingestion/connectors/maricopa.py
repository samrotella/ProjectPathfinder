"""Maricopa County, AZ connector — BULK EXPORT access pattern.

Real source: the Recorder's Office sells bulk index + image exports. The index
carries AZ's required document caption (A.R.S. 11-480), which gives a clean
document-type field to filter on. The production `fetch` would read the most
recent purchased export drop (CSV/fixed-width) from a configured directory.

For the MVP, `fetch` reads a bundled sample file with the same field shape.
Point `data_path` at a real export file to ingest live data unchanged.

Deliberately different from the Miami-Dade connector (a live feed) so the
canonical schema is proven against two unlike source models from day one.
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

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "maricopa_sample.json"

# Caption text -> canonical type. Longest match wins, so "RELEASE OF MECHANICS
# LIEN" resolves to a release rather than a lien.
_DOC_TYPE_MAP = {
    "RELEASE OF MECHANICS LIEN": DocumentType.LIEN_RELEASE,
    "RELEASE OF LIEN": DocumentType.LIEN_RELEASE,
    "NOTICE OF COMPLETION": DocumentType.NOTICE_OF_COMPLETION,
    "PRELIMINARY TWENTY DAY NOTICE": DocumentType.PRELIMINARY_NOTICE,
    "TWENTY DAY NOTICE": DocumentType.PRELIMINARY_NOTICE,
    "MECHANICS LIEN": DocumentType.MECHANICS_LIEN,
}

_RELEVANT_CAPTIONS = ("LIEN", "TWENTY DAY NOTICE", "NOTICE OF COMPLETION")


class MaricopaConnector(SourceConnector):
    source_id = "maricopa-az"
    jurisdiction = "Maricopa County, AZ"
    county = "Maricopa"
    state = "AZ"

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or _FIXTURE

    def fetch(self, since: date | None = None) -> Iterable[RawRecord]:
        records = json.loads(self.data_path.read_text())
        for rec in records:
            caption = (rec.get("caption") or "").upper()
            if not any(token in caption for token in _RELEVANT_CAPTIONS):
                continue
            if since:
                rd = parse_date(rec.get("record_date"))
                if rd and rd < since:
                    continue
            yield rec

    def to_canonical(self, raw: RawRecord) -> CanonicalLienInput:
        doc_type = map_document_type(raw.get("caption"), _DOC_TYPE_MAP)
        amount = parse_amount(raw.get("amount")) if doc_type == DocumentType.MECHANICS_LIEN else None
        rec_no = str(raw["recording_number"])
        return CanonicalLienInput(
            source_id=self.source_id,
            source_record_id=rec_no,
            source_url=f"https://recorder.maricopa.gov/recdocdata/GetRecDataDetail.aspx?rec={rec_no}",
            document_number=rec_no,
            recording_date=parse_date(raw.get("record_date")),
            document_type=doc_type,
            raw_document_type=raw.get("caption"),
            # In an AZ mechanics lien the recording claimant is the grantor and
            # the property owner is the grantee. Simplified for the MVP.
            claimant_name=clean_name(raw.get("grantor")),
            owner_name=clean_name(raw.get("grantee")),
            property_address=raw.get("situs_address"),
            parcel_id=raw.get("apn"),
            legal_description=raw.get("legal"),
            amount_claimed=amount,
            related_document_number=raw.get("references_recording_number"),
            jurisdiction=self.jurisdiction,
            county=self.county,
            state=self.state,
            raw=raw,
        )
