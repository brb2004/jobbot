import asyncio
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, field_validator
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job

API = "https://boards-api.greenhouse.io/v1/boards"


class BoardJob(BaseModel):
    id: int
    title: str
    absolute_url: str
    updated_at: str | None = None
    location: str | None = None

    @field_validator("location", mode="before")
    @classmethod
    def flatten_location(cls, v):
        return v.get("name") if isinstance(v, dict) else v


@dataclass
class CrawlSummary:
    found: int = 0
    missing: int = 0
    failed: int = 0
    new_jobs: int = 0


async def fetch_board(client: httpx.AsyncClient, slug: str) -> list[BoardJob] | None:
    r = await client.get(f"{API}/{slug}/jobs")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return [BoardJob.model_validate(j) for j in r.json()["jobs"]]


async def save_board(s: AsyncSession, board: str, jobs: list[BoardJob]) -> int:
    if not jobs:
        return 0
    stmt = insert(Job).values([
        {"board": board, "external_id": j.id, "title": j.title,
         "url": j.absolute_url, "location": j.location}
        for j in jobs
    ])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_jobs_board_external",
        set_={"title": stmt.excluded.title, "url": stmt.excluded.url,
              "location": stmt.excluded.location},
    ).returning(literal_column("xmax = 0"))
    inserted = (await s.execute(stmt)).scalars().all()
    await s.commit()
    return sum(inserted)


async def crawl(client: httpx.AsyncClient, s: AsyncSession, slugs: list[str],
                concurrency: int = 4) -> CrawlSummary:
    sem = asyncio.Semaphore(concurrency)

    async def fetch(slug):
        async with sem:
            try:
                return slug, await fetch_board(client, slug), None
            except httpx.HTTPError as e:
                return slug, None, e

    results = await asyncio.gather(*(fetch(slug) for slug in slugs))

    summary = CrawlSummary()
    for slug, jobs, err in results:
        if err:
            summary.failed += 1
        elif jobs is None:
            summary.missing += 1
        else:
            summary.found += 1
            summary.new_jobs += await save_board(s, slug, jobs)
    return summary