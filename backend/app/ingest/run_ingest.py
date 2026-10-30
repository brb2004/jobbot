import asyncio
import sys

import httpx

from app.core.db_core import SessionLocal, engine
from app.ingest.greenhouse_ingest import crawl, fill_descriptions

SLUGS = ["stripe", "figma", "vercel", "airbnb", "discord", "databricks", "cloudflare",
         "dropbox", "reddit", "robinhood", "coinbase", "instacart", "lyft", "pinterest",
         "duolingo", "gitlab", "twitch", "doordash", "asana", "brex", "plaid"]


async def main(slugs: list[str]) -> None:
    headers = {"User-Agent": "jobbot3-crawler (github.com/brb2004)"}
    async with httpx.AsyncClient(timeout=15, headers=headers) as client, SessionLocal() as s:
        summary = await crawl(client, s, slugs)
        filled = await fill_descriptions(client, s)
    await engine.dispose()
    print(summary, f"descriptions filled: {filled}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or SLUGS))