import asyncio
import contextlib
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Board, Job
from app.ingest.upsert_ingest import deferred_upsert, inline_upsert, upsert

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
    rows = [_row(key, p) for p in postings]
    deferred = [r for r in rows if "content_html" not in r]
    inline = [r for r in rows if "content_html" in r]
    new = await upsert(s, deferred_upsert, deferred) + await upsert(s, inline_upsert, inline)
    if rows:
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
            await _store(s, key, got, name, summary)
    return summary


async def _store(s: AsyncSession, key: str, got, name: str | None, summary: CrawlSummary) -> None:
    postings, listed = got
    try:
        if name:
            await save_name(s, key, name)
        await s.execute(update(Board).where(Board.slug == key, Board.misses > 0).values(misses=0))
        summary.new_jobs += await save_postings(s, key, postings)
        summary.closed += await close_missing(s, key, listed)
    except SQLAlchemyError as e:
        await s.rollback()
        log.warning("board %s could not be saved: %s", key, repr(e)[:200])
        summary.failed += 1
        return
    summary.found += 1
