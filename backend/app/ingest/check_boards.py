"""Check every slug in boards.txt against the Greenhouse API. 404 = wrong slug or not on Greenhouse."""
import asyncio

import httpx

from app.ingest.run_ingest import BOARDS_FILE, HEADERS, load_slugs

API = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"


async def check(client: httpx.AsyncClient, sem: asyncio.Semaphore, slug: str) -> tuple[str, str]:
    async with sem:
        try:
            r = await client.get(API.format(slug))
        except httpx.HTTPError as e:
            return slug, f"ERROR {type(e).__name__}"
    return slug, f"{len(r.json()['jobs'])} jobs" if r.status_code == 200 else f"BAD ({r.status_code})"


async def main() -> None:
    sem = asyncio.Semaphore(5)                                 # be polite: 5 at a time
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        results = await asyncio.gather(*(check(client, sem, s) for s in load_slugs(BOARDS_FILE.read_text())))
    for slug, status in sorted(results, key=lambda r: r[1].startswith("BAD"), reverse=True):
        print(f"{slug:24} {status}")


if __name__ == "__main__":
    asyncio.run(main())
