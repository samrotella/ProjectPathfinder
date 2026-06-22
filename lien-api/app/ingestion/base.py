"""The connector contract.

Adding a jurisdiction means writing one class that implements `fetch` (get raw
records from wherever the source lives) and `to_canonical` (map one raw record
into the canonical schema). Everything downstream — dedup, storage, search,
serving — is source-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

from app.schemas import CanonicalLienInput

RawRecord = dict


class SourceConnector(ABC):
    #: Stable identifier for this source, e.g. "maricopa-az".
    source_id: str
    jurisdiction: str
    county: str
    state: str

    @abstractmethod
    def fetch(self, since: date | None = None) -> Iterable[RawRecord]:
        """Yield raw source records, optionally only those on/after `since`.

        Implementations encapsulate the access pattern (HTTP API, FTP bulk file,
        purchased export, scrape) so the rest of the system never sees it.
        """

    @abstractmethod
    def to_canonical(self, raw: RawRecord) -> CanonicalLienInput:
        """Map a single raw record into the canonical schema."""
