import asyncio
import sys
from pathlib import Path

import httpx

from app.core.db_core import SessionLocal, engine
from app.ingest.greenhouse_ingest import crawl, fill_descriptions

BOARDS_FILE = Path(__file__).resolve().parents[2] / "boards.txt"   # backend/boards.txt
HEADERS = {"User-Agent": "jobbot3-crawler (github.com/brb2004)"}


def load_slugs(text: str) -> list[str]:
    slugs: list[str] = []
    for line in text.splitlines():
        slug = line.split("#", 1)[0].strip().lower()
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


async def main(slugs: list[str]) -> None:
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client, SessionLocal() as s:
        summary = await crawl(client, s, slugs)
        filled = await fill_descriptions(client, s)
    await engine.dispose()
    print(summary, f"descriptions filled: {filled}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or load_slugs(BOARDS_FILE.read_text())))
