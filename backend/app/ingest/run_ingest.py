"""Crawl every board in boards.txt (all sources), close what's gone, fill Greenhouse details, prune.

python -m app.ingest.run_ingest                    # full crawl
python -m app.ingest.run_ingest stripe ashby:ramp  # just these (retires nothing)
"""

import asyncio
import sys

import httpx

from app.core.db_core import SessionLocal, engine
from app.ingest.boards_ingest import BOARDS_FILE, HEADERS, by_source, load_slugs
from app.ingest.crawl_ingest import crawl_source, retire_dropped
from app.ingest.greenhouse_ingest import fill_descriptions
from app.services.retention_services import prune

__all__ = ["BOARDS_FILE", "HEADERS", "by_source", "load_slugs", "main"]


async def main(keys: list[str], full: bool) -> None:
    groups = by_source(keys)
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client, SessionLocal() as s:
        for source, slugs in groups.items():
            if slugs:
                print(source.name, await crawl_source(client, s, source, slugs))
        if full:  # only a full crawl may retire other boards
            print(f"jobs closed from boards no longer listed: {await retire_dropped(s, keys)}")
        filled = await fill_descriptions(client, s)
        pruned = await prune(s)
    await engine.dispose()
    print(f"descriptions filled: {filled}", pruned)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or load_slugs(BOARDS_FILE.read_text()), full=not sys.argv[1:]))
