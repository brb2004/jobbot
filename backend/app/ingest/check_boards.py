import asyncio

import httpx

from app.ingest.boards_ingest import BOARDS_FILE, HEADERS, by_source, load_slugs


async def check(client: httpx.AsyncClient, sem: asyncio.Semaphore, source, slug: str) -> tuple[str, str]:
    async with sem:
        try:
            got = await source.fetch_board(client, slug)
        except Exception as e:
            return source.key(slug), f"ERROR {type(e).__name__}"
    return source.key(slug), "BAD (404)" if got is None else f"{len(got[1])} jobs"


async def main() -> None:
    sem = asyncio.Semaphore(5)
    groups = by_source(load_slugs(BOARDS_FILE.read_text()))
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        results = await asyncio.gather(
            *(check(client, sem, src, s) for src, slugs in groups.items() for s in slugs)
        )
    for key, status in sorted(results, key=lambda r: r[1].startswith(("BAD", "ERROR")), reverse=True):
        print(f"{key:32} {status}")


if __name__ == "__main__":
    asyncio.run(main())
