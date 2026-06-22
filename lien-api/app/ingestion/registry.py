"""Registry of active connectors. Adding a jurisdiction = adding one line here."""
from __future__ import annotations

from app.ingestion.base import SourceConnector
from app.ingestion.connectors.maricopa import MaricopaConnector
from app.ingestion.connectors.miami_dade import MiamiDadeConnector


def default_connectors() -> list[SourceConnector]:
    return [MiamiDadeConnector(), MaricopaConnector()]
