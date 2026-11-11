import asyncio
import html as htmllib
import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, field_validator
from sqlalchemy import case, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.batches_db import batches
from app.db.models_db import Board, Job
from app.ingest.text_ingest import html_to_text

API = "https://boards-api.greenhouse.io/v1/boards"
TRIES = 3            # attempts per request on 429 / 5xx / connection errors
BACKOFF = 0.5        # seconds, doubled each retry (Retry-After wins when it's longer, capped at 10 s)
MAX_MISSES = 3       # consecutive 404 crawls before a board's jobs are closed
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


class JobDetails(BaseModel):
    description: str
    content_html: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None


@dataclass
class CrawlSummary:
    found: int = 0
    missing: int = 0
    failed: int = 0
    new_jobs: int = 0
    closed: int = 0


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> httpx.Response:
    """GET with retries for the failures that pass: 429 (rate limited), 5xx and dropped connections."""
    for attempt in range(TRIES):
        wait = BACKOFF * 2 ** attempt
        try:
            r = await client.get(url, params=params)
        except httpx.TransportError:
            if attempt == TRIES - 1:
                raise
        else:
            if (r.status_code != 429 and r.status_code < 500) or attempt == TRIES - 1:
                return r
            try:
                wait = max(wait, float(r.headers.get("Retry-After", 0)))
            except ValueError:
                pass
        await asyncio.sleep(min(wait, 10))
    raise AssertionError("unreachable")


async def fetch_board(client: httpx.AsyncClient, slug: str) -> tuple[list[BoardJob], list[int]] | None:
    """(jobs that parsed, ids of everything listed) or None for 404. One malformed job is skipped, not fatal,
    and its id still counts as listed, so it isn't closed by mistake."""
    r = await _get(client, f"{API}/{slug}/jobs")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    raw = r.json()["jobs"]                                  # not JSON / no "jobs": the whole board fails
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
    """The company's real name: slugs can be "accenturefederalservices" or a random id like "a3c41b8b71eff8c4"."""
    r = await _get(client, f"{API}/{slug}")
    if r.status_code != 200:
        return None
    return (r.json().get("name") or "").strip()[:200] or None


async def save_name(s: AsyncSession, slug: str, name: str) -> None:
    stmt = insert(Board).values(slug=slug, name=name, checked_at=func.now())
    await s.execute(stmt.on_conflict_do_update(index_elements=[Board.slug],
                                               set_={"name": stmt.excluded.name, "checked_at": func.now()}))


async def fetch_details(client: httpx.AsyncClient, board: str, job_id: int) -> JobDetails:
    r = await _get(client, f"{API}/{board}/jobs/{job_id}", params={"pay_transparency": "true"})
    r.raise_for_status()
    data = r.json()
    pay = (data.get("pay_input_ranges") or [{}])[0]

    def dollars(cents):
        return cents / 100 if cents is not None else None

    raw = data.get("content") or ""
    if "&lt;" in raw:
        raw = htmllib.unescape(raw)     # Greenhouse double-encodes
    return JobDetails(
        description=html_to_text(raw),
        content_html=raw,
        salary_min=dollars(pay.get("min_cents")),
        salary_max=dollars(pay.get("max_cents")),
        salary_currency=pay.get("currency_type"),
    )


async def save_board(s: AsyncSession, board: str, jobs: list[BoardJob]) -> int:
    if not jobs:
        return 0
    stmt = insert(Job).values([
        {"board": board, "external_id": j.id, "title": j.title.strip(),
         "url": j.absolute_url, "location": j.location, "source_updated_at": j.updated_at}
        for j in jobs
    ])
    # The company edited the posting since we fetched it: drop the description so fill_descriptions
    # fetches it again. Skills and requirements stay until the new text replaces them, so the job keeps
    # matching meanwhile. NULL before (rows from before this column existed) is not a change.
    edited = Job.source_updated_at.is_not(None) & Job.source_updated_at.is_distinct_from(stmt.excluded.source_updated_at)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_jobs_board_external",
        set_={"title": stmt.excluded.title, "url": stmt.excluded.url,
              "location": stmt.excluded.location,
              "description": case((edited, None), else_=Job.description),
              "source_updated_at": stmt.excluded.source_updated_at,
              "closed_at": None},                               # listed again -> open again
    ).returning(literal_column("xmax = 0"))
    inserted = (await s.execute(stmt)).scalars().all()
    await s.commit()
    return sum(inserted)


async def close_missing(s: AsyncSession, board: str, listed_ids: list[int]) -> int:
    """Close this board's open jobs that the board no longer lists. Only call after a SUCCESSFUL fetch."""
    stmt = (update(Job)
            .where(Job.board == board, Job.closed_at.is_(None), Job.external_id.not_in(listed_ids or [-1]))
            .values(closed_at=func.now()))
    closed = (await s.execute(stmt)).rowcount
    await s.commit()
    return closed


async def note_missing(s: AsyncSession, slug: str) -> int:
    """A board answered 404. After MAX_MISSES crawls in a row, close its jobs (one 404 can be a blip)."""
    stmt = insert(Board).values(slug=slug, misses=1, checked_at=func.now())
    stmt = stmt.on_conflict_do_update(index_elements=[Board.slug],
                                      set_={"misses": Board.misses + 1, "checked_at": func.now()})
    misses = (await s.execute(stmt.returning(Board.misses))).scalar_one()
    closed = 0
    if misses >= MAX_MISSES:
        closed = (await s.execute(update(Job).where(Job.board == slug, Job.closed_at.is_(None))
                                  .values(closed_at=func.now()))).rowcount
    await s.commit()
    return closed


async def retire_dropped(s: AsyncSession, slugs: list[str]) -> int:
    """Close open jobs from boards no longer in the crawl list. Run only after crawling the FULL list."""
    closed = (await s.execute(update(Job).where(Job.closed_at.is_(None), Job.board.is_not(None),
                                                Job.board.not_in(slugs or ["-"]))
                              .values(closed_at=func.now()))).rowcount
    await s.commit()
    return closed


async def crawl(client: httpx.AsyncClient, s: AsyncSession, slugs: list[str],
                concurrency: int = 4) -> CrawlSummary:
    sem = asyncio.Semaphore(concurrency)
    named = set((await s.scalars(select(Board.slug).where(Board.name.is_not(None)))).all())

    async def fetch(slug):
        async with sem:
            try:
                got = await fetch_board(client, slug)
            except Exception as e:                                  # any failure: this board only
                log.warning("board %s failed: %s", slug, repr(e)[:200])
                return slug, None, e, None
            name = None
            if got is not None and slug not in named:               # once per board, not every crawl
                try:
                    name = await fetch_board_name(client, slug)
                except Exception:
                    pass                                            # try again next crawl
            return slug, got, None, name

    summary = CrawlSummary()
    tasks = [asyncio.ensure_future(fetch(slug)) for slug in slugs]
    for done in asyncio.as_completed(tasks):                   # save each board as it lands, then drop it
        slug, got, err, name = await done
        if err:
            summary.failed += 1                                 # unknown state: close nothing
        elif got is None:
            summary.missing += 1                                # 404: counted; closed after MAX_MISSES in a row
            summary.closed += await note_missing(s, slug)
        else:
            jobs, listed = got
            summary.found += 1
            if name:
                await save_name(s, slug, name)                      # committed with the board's jobs
            await s.execute(update(Board).where(Board.slug == slug, Board.misses > 0).values(misses=0))
            summary.new_jobs += await save_board(s, slug, jobs)
            summary.closed += await close_missing(s, slug, listed)
    return summary


async def fill_descriptions(client: httpx.AsyncClient, s: AsyncSession,
                            concurrency: int = 8) -> int:
    """Details for open jobs that lack them, a batch at a time: memory stays flat and each batch is
    committed, so a killed run keeps what it finished and the next run picks up the rest."""
    stmt = select(Job).where(
        Job.description.is_(None),
        Job.board.is_not(None),
        Job.external_id.is_not(None),
        Job.closed_at.is_(None),                                # don't fetch details for dead postings
    )
    sem = asyncio.Semaphore(concurrency)

    async def fetch(job):
        async with sem:
            try:
                return job, await fetch_details(client, job.board, job.external_id)
            except Exception as e:                              # one bad posting never stops the run
                log.warning("details %s/%s failed: %s", job.board, job.external_id, repr(e)[:200])
                return job, None

    filled = 0
    async for jobs in batches(s, stmt, Job.id):
        for job, d in await asyncio.gather(*(fetch(j) for j in jobs)):
            if d is None:
                continue                                        # stays empty: retried next run
            job.description = d.description
            job.content_html = d.content_html
            job.salary_min, job.salary_max, job.salary_currency = d.salary_min, d.salary_max, d.salary_currency
            job.requirements, job.skills_version = None, None    # re-extracted and re-tagged from the new text
            filled += 1
        await s.commit()
    return filled
