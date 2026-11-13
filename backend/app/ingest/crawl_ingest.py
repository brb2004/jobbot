"""The crawl loop every job source shares. A source is an adapter: fetch one board -> normalized Postings.

Board keys: Greenhouse boards keep their plain slug ("stripe"); other sources are namespaced
("ashby:ramp", "lever:spotify"). jobs.board and boards.slug hold the key, so matching, per-company
limits and company names work the same for every source.
"""

import asyncio
import contextlib
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import case, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Board, Job

TRIES = 3  # attempts per request on 429 / 5xx / connection errors
BACKOFF = 0.5  # seconds, doubled each retry (Retry-After wins when it's longer, capped at 10 s)
MAX_MISSES = 3  # consecutive 404 crawls before a board's jobs are closed
log = logging.getLogger(__name__)


@dataclass
class Posting:
    """One job as every source reports it. content_html None = the source sends details separately
    (Greenhouse: fill_descriptions fetches them); set = the listing carried the full posting."""

    external_id: str
    title: str
    url: str
    location: str | None = None
    version: str | None = None  # changes when the posting changes (Greenhouse updated_at, else a hash)
    content_html: str | None = None
    description: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None


Listing = tuple[list[Posting], list[str]]  # (postings that parsed, ids of everything listed)


@dataclass(frozen=True)
class Source:
    name: str
    prefix: str  # "" for Greenhouse, else "ashby:" ...
    fetch_board: Callable[[httpx.AsyncClient, str], Awaitable[Listing | None]]  # None = 404
    fetch_name: Callable[[httpx.AsyncClient, str], Awaitable[str | None]]

    def key(self, slug: str) -> str:
        return self.prefix + slug


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
        wait = BACKOFF * 2**attempt
        try:
            r = await client.get(url, params=params)
        except httpx.TransportError:
            if attempt == TRIES - 1:
                raise
        else:
            if (r.status_code != 429 and r.status_code < 500) or attempt == TRIES - 1:
                return r
            with contextlib.suppress(ValueError):  # a date-form Retry-After: keep our own backoff
                wait = max(wait, float(r.headers.get("Retry-After", 0)))
        await asyncio.sleep(min(wait, 10))
    raise AssertionError("unreachable")


def fingerprint(*parts: str | None) -> str:
    """Version for sources without an updated_at: changes exactly when the posting's content does."""
    return hashlib.sha256("\x1f".join(p or "" for p in parts).encode()).hexdigest()[:32]


def name_from_slug(slug: str) -> str:
    """Display name when the source's API doesn't send one: "acme-corp" -> "Acme Corp"."""
    words = re.split(r"[-_.\s]+", slug.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)[:200] or slug


def remote_location(pieces: list[str], remote: bool) -> str | None:
    """Join locations with "; " (how matching splits them). A remote job's pieces say so, so
    preferences treat "Remote - United States" like a Greenhouse posting that wrote it that way."""
    pieces = [p.strip() for p in pieces if p and p.strip()]
    pieces = list(dict.fromkeys(pieces))  # dedupe, keep order
    if remote:
        pieces = [p if re.search(r"(?i)\bremote\b", p) else f"Remote - {p}" for p in pieces] or ["Remote"]
    return "; ".join(pieces) or None


async def save_name(s: AsyncSession, key: str, name: str) -> None:
    stmt = insert(Board).values(slug=key, name=name, checked_at=func.now())
    await s.execute(
        stmt.on_conflict_do_update(
            index_elements=[Board.slug], set_={"name": stmt.excluded.name, "checked_at": func.now()}
        )
    )


def _row(key: str, p: Posting) -> dict:
    row = {
        "board": key,
        "external_id": p.external_id,
        "title": " ".join(p.title.split()),
        "url": p.url,
        "location": p.location,
        "source_updated_at": p.version,
    }
    if p.content_html is not None:
        row |= {
            "content_html": p.content_html,
            "description": p.description,
            "salary_min": p.salary_min,
            "salary_max": p.salary_max,
            "salary_currency": p.salary_currency,
        }
    return row


async def save_postings(s: AsyncSession, key: str, postings: list[Posting]) -> int:
    """Upsert one board's postings; returns how many are new. Listed again -> open again."""
    if not postings:
        return 0
    inline = [p for p in postings if p.content_html is not None]
    deferred = [p for p in postings if p.content_html is None]
    new = 0
    if deferred:
        stmt = insert(Job).values([_row(key, p) for p in deferred])
        # The company edited the posting since we fetched it: drop the description so fill_descriptions
        # fetches it again. Skills and requirements stay until the new text replaces them, so the job keeps
        # matching meanwhile. NULL before (rows from before this column existed) is not a change.
        edited = Job.source_updated_at.is_not(None) & Job.source_updated_at.is_distinct_from(
            stmt.excluded.source_updated_at
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_jobs_board_external",
            set_={
                "title": stmt.excluded.title,
                "url": stmt.excluded.url,
                "location": stmt.excluded.location,
                "description": case((edited, None), else_=Job.description),
                "source_updated_at": stmt.excluded.source_updated_at,
                "closed_at": None,
            },
        ).returning(literal_column("xmax = 0"))
        new += sum((await s.execute(stmt)).scalars().all())
    if inline:
        stmt = insert(Job).values([_row(key, p) for p in inline])
        x = stmt.excluded
        # The listing carries the whole posting: take the new text when it changed (or was pruned while
        # closed) and clear requirements/skills so extraction and tagging rebuild them from it.
        changed = Job.source_updated_at.is_distinct_from(x.source_updated_at) | Job.content_html.is_(None)
        fresh = {
            c: case((changed, getattr(x, c)), else_=getattr(Job, c))
            for c in ("content_html", "description", "salary_min", "salary_max", "salary_currency")
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_jobs_board_external",
            set_={
                "title": x.title,
                "url": x.url,
                "location": x.location,
                **fresh,
                "requirements": case((changed, None), else_=Job.requirements),
                "skills_version": case((changed, None), else_=Job.skills_version),
                "source_updated_at": x.source_updated_at,
                "closed_at": None,
            },
        ).returning(literal_column("xmax = 0"))
        new += sum((await s.execute(stmt)).scalars().all())
    await s.commit()
    return new


async def close_missing(s: AsyncSession, key: str, listed_ids: list[str]) -> int:
    """Close this board's open jobs that the board no longer lists. Only call after a SUCCESSFUL fetch."""
    stmt = (
        update(Job)
        .where(Job.board == key, Job.closed_at.is_(None), Job.external_id.not_in(listed_ids or ["-"]))
        .values(closed_at=func.now())
    )
    closed = (await s.execute(stmt)).rowcount
    await s.commit()
    return closed


async def note_missing(s: AsyncSession, key: str) -> int:
    """A board answered 404. After MAX_MISSES crawls in a row, close its jobs (one 404 can be a blip)."""
    stmt = insert(Board).values(slug=key, misses=1, checked_at=func.now())
    stmt = stmt.on_conflict_do_update(
        index_elements=[Board.slug], set_={"misses": Board.misses + 1, "checked_at": func.now()}
    )
    misses = (await s.execute(stmt.returning(Board.misses))).scalar_one()
    closed = 0
    if misses >= MAX_MISSES:
        closed = (
            await s.execute(
                update(Job).where(Job.board == key, Job.closed_at.is_(None)).values(closed_at=func.now())
            )
        ).rowcount
    await s.commit()
    return closed


async def retire_dropped(s: AsyncSession, keys: list[str]) -> int:
    """Close open jobs from boards no longer in the crawl list (every source's keys).
    Run only after crawling the FULL list of every source."""
    closed = (
        await s.execute(
            update(Job)
            .where(Job.closed_at.is_(None), Job.board.is_not(None), Job.board.not_in(keys or ["-"]))
            .values(closed_at=func.now())
        )
    ).rowcount
    await s.commit()
    return closed


async def crawl_source(
    client: httpx.AsyncClient, s: AsyncSession, source: Source, slugs: list[str], concurrency: int = 4
) -> CrawlSummary:
    sem = asyncio.Semaphore(concurrency)
    named = set((await s.scalars(select(Board.slug).where(Board.name.is_not(None)))).all())

    async def fetch(slug):
        async with sem:
            try:
                got = await source.fetch_board(client, slug)
            except Exception as e:  # any failure: this board only
                log.warning("%s board %s failed: %s", source.name, slug, repr(e)[:200])
                return slug, None, e, None
            name = None
            if got is not None and source.key(slug) not in named:  # once per board, not every crawl
                with contextlib.suppress(Exception):  # try again next crawl
                    name = await source.fetch_name(client, slug)
            return slug, got, None, name

    summary = CrawlSummary()
    tasks = [asyncio.ensure_future(fetch(slug)) for slug in slugs]
    for done in asyncio.as_completed(tasks):  # save each board as it lands, then drop it
        slug, got, err, name = await done
        key = source.key(slug)
        if err:
            summary.failed += 1  # unknown state: close nothing
        elif got is None:
            summary.missing += 1  # 404: counted; closed after MAX_MISSES in a row
            summary.closed += await note_missing(s, key)
        else:
            postings, listed = got
            summary.found += 1
            if name:
                await save_name(s, key, name)  # committed with the board's jobs
            await s.execute(update(Board).where(Board.slug == key, Board.misses > 0).values(misses=0))
            summary.new_jobs += await save_postings(s, key, postings)
            summary.closed += await close_missing(s, key, listed)
    return summary
