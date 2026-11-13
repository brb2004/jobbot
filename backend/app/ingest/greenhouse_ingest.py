import asyncio
import html as htmllib
import logging

import httpx
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.batches_db import batches
from app.db.models_db import Job
from app.ingest.crawl_ingest import (
    CrawlSummary,
    Posting,
    Source,
    _get,
    crawl_source,
    note_missing,
    retire_dropped,
    save_name,
    save_postings,
)
from app.ingest.crawl_ingest import (
    close_missing as _close_missing,
)
from app.ingest.text_ingest import html_to_text

__all__ = [
    "API",
    "BoardJob",
    "JobDetails",
    "CrawlSummary",
    "fetch_board",
    "fetch_board_name",
    "fetch_details",
    "save_board",
    "save_name",
    "close_missing",
    "note_missing",
    "retire_dropped",
    "crawl",
    "fill_descriptions",
    "GREENHOUSE",
    "_get",
]

API = "https://boards-api.greenhouse.io/v1/boards"
log = logging.getLogger(__name__)


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

    def posting(self) -> Posting:
        return Posting(
            external_id=str(self.id),
            title=self.title,
            url=self.absolute_url,
            location=self.location,
            version=self.updated_at,
        )


class JobDetails(BaseModel):
    description: str
    content_html: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None


async def fetch_board(client: httpx.AsyncClient, slug: str) -> tuple[list[BoardJob], list[int]] | None:
    r = await _get(client, f"{API}/{slug}/jobs")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    raw = r.json()["jobs"]  # not JSON / no "jobs": the whole board fails
    jobs, ids = [], []
    for j in raw:
        if isinstance(j, dict) and isinstance(j.get("id"), int):
            ids.append(j["id"])
        try:
            jobs.append(BoardJob.model_validate(j))
        except Exception as e:
            log.warning("board %s: skipped a malformed job: %s", slug, str(e)[:200])
    return jobs, ids


async def fetch_board_name(client: httpx.AsyncClient, slug: str) -> str | None:
    r = await _get(client, f"{API}/{slug}")
    if r.status_code != 200:
        return None
    return (r.json().get("name") or "").strip()[:200] or None


async def _listing(client: httpx.AsyncClient, slug: str):
    got = await fetch_board(client, slug)
    if got is None:
        return None
    jobs, ids = got
    return [j.posting() for j in jobs], [str(i) for i in ids]


GREENHOUSE = Source(name="greenhouse", prefix="", fetch_board=_listing, fetch_name=fetch_board_name)


async def save_board(s: AsyncSession, board: str, jobs: list[BoardJob]) -> int:
    return await save_postings(s, board, [j.posting() for j in jobs])


async def close_missing(s: AsyncSession, board: str, listed_ids: list[int | str]) -> int:
    return await _close_missing(s, board, [str(i) for i in listed_ids])


async def crawl(
    client: httpx.AsyncClient, s: AsyncSession, slugs: list[str], concurrency: int = 4
) -> CrawlSummary:
    return await crawl_source(client, s, GREENHOUSE, slugs, concurrency)


async def fetch_details(client: httpx.AsyncClient, board: str, job_id: int | str) -> JobDetails:
    r = await _get(client, f"{API}/{board}/jobs/{job_id}", params={"pay_transparency": "true"})
    r.raise_for_status()
    data = r.json()
    pay = (data.get("pay_input_ranges") or [{}])[0]

    def dollars(cents):
        return cents / 100 if cents is not None else None

    raw = data.get("content") or ""
    if "&lt;" in raw:
        raw = htmllib.unescape(raw)  # Greenhouse double-encodes
    return JobDetails(
        description=html_to_text(raw),
        content_html=raw,
        salary_min=dollars(pay.get("min_cents")),
        salary_max=dollars(pay.get("max_cents")),
        salary_currency=pay.get("currency_type"),
    )


async def fill_descriptions(client: httpx.AsyncClient, s: AsyncSession, concurrency: int = 8) -> int:
    stmt = select(Job).where(
        Job.description.is_(None),
        Job.board.is_not(None),
        Job.board.not_like("%:%"),  # Greenhouse keys have no source prefix
        Job.external_id.is_not(None),
        Job.closed_at.is_(None),  # don't fetch details for dead postings
    )
    sem = asyncio.Semaphore(concurrency)

    async def fetch(job):
        async with sem:
            try:
                return job, await fetch_details(client, job.board, job.external_id)
            except Exception as e:  # one bad posting never stops the run
                log.warning("details %s/%s failed: %s", job.board, job.external_id, repr(e)[:200])
                return job, None

    filled = 0
    async for jobs in batches(s, stmt, Job.id):
        for job, d in await asyncio.gather(*(fetch(j) for j in jobs)):
            if d is None:
                continue  # stays empty: retried next run
            job.description = d.description
            job.content_html = d.content_html
            job.salary_min, job.salary_max, job.salary_currency = (
                d.salary_min,
                d.salary_max,
                d.salary_currency,
            )
            job.requirements, job.skills_version = None, None  # re-extracted and re-tagged from the new text
            filled += 1
        await s.commit()
    return filled
