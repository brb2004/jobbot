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

TRIES = 3
BACKOFF = 0.5
MAX_MISSES = 3
log = logging.getLogger(__name__)


@dataclass
class Posting:
    external_id: str
    title: str
    url: str
    location: str | None = None
    version: str | None = None
    content_html: str | None = None
    description: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None


Listing = tuple[list[Posting], list[str]]


@dataclass(frozen=True)
class Source:
    name: str
    prefix: str
    fetch_board: Callable[[httpx.AsyncClient, str], Awaitable[Listing | None]]
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
            with contextlib.suppress(ValueError):
                wait = max(wait, float(r.headers.get("Retry-After", 0)))
        await asyncio.sleep(min(wait, 10))
    raise AssertionError("unreachable")


def fingerprint(*parts: str | None) -> str:
    return hashlib.sha256("\x1f".join(p or "" for p in parts).encode()).hexdigest()[:32]


def name_from_slug(slug: str) -> str:
    words = re.split(r"[-_.\s]+", slug.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)[:200] or slug


def remote_location(pieces: list[str], remote: bool) -> str | None:
    pieces = [p.strip() for p in pieces if p and p.strip()]
    pieces = list(dict.fromkeys(pieces))
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
    if not postings:
        return 0
    inline = [p for p in postings if p.content_html is not None]
    deferred = [p for p in postings if p.content_html is None]
    new = 0
    if deferred:
        stmt = insert(Job).values([_row(key, p) for p in deferred])
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
    stmt = (
        update(Job)
        .where(Job.board == key, Job.closed_at.is_(None), Job.external_id.not_in(listed_ids or ["-"]))
        .values(closed_at=func.now())
    )
    closed = (await s.execute(stmt)).rowcount
    await s.commit()
    return closed


async def note_missing(s: AsyncSession, key: str) -> int:
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
            except Exception as e:
                log.warning("%s board %s failed: %s", source.name, slug, repr(e)[:200])
                return slug, None, e, None
            name = None
            if got is not None and source.key(slug) not in named:
                with contextlib.suppress(Exception):
                    name = await source.fetch_name(client, slug)
            return slug, got, None, name

    summary = CrawlSummary()
    tasks = [asyncio.ensure_future(fetch(slug)) for slug in slugs]
    for done in asyncio.as_completed(tasks):
        slug, got, err, name = await done
        key = source.key(slug)
        if err:
            summary.failed += 1
        elif got is None:
            summary.missing += 1
            summary.closed += await note_missing(s, key)
        else:
            postings, listed = got
            summary.found += 1
            if name:
                await save_name(s, key, name)
            await s.execute(update(Board).where(Board.slug == key, Board.misses > 0).values(misses=0))
            summary.new_jobs += await save_postings(s, key, postings)
            summary.closed += await close_missing(s, key, listed)
    return summary
