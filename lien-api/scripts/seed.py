"""Run the ingestion pipeline against the bundled sample data.

    python -m scripts.seed

Creates tables (dev/SQLite) and ingests every registered connector's records,
then prints a summary. Swap fixtures for real downloaded feeds/exports by passing
`data_path` to the connectors in app/ingestion/registry.py.
"""
from __future__ import annotations

import asyncio

from app.database import SessionLocal, init_db
from app.ingestion.pipeline import run_pipeline
from app.ingestion.registry import default_connectors


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        stats = await run_pipeline(session, default_connectors())
    print("Ingestion complete:")
    print(f"  inserted:        {stats.inserted}")
    print(f"  updated:         {stats.updated}")
    print(f"  releases linked: {stats.releases_linked}")
    print(f"  by source:       {stats.by_source}")


if __name__ == "__main__":
    asyncio.run(main())
