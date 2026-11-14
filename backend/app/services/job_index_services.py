import asyncio
import time
from dataclasses import dataclass

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job
from app.services.requirements_services import (
    needs_clearance,
    years_from_pitch,
    years_from_title,
    years_required,
)
from app.services.scoring_services import build_index, idf_weights
from app.services.skills_services import default_tagger
from app.services.titles_services import role_key

MAX_AGE_S = 3600
OPEN = (Job.skills.is_not(None), Job.closed_at.is_(None))
_ROWS = select(Job.id, Job.board, Job.title, Job.location, Job.skills, Job.requirements).where(*OPEN)


@dataclass(frozen=True)
class JobRow:
    id: object
    board: str | None
    title: str | None
    location: str | None


@dataclass(frozen=True)
class JobIndex:
    jobs: list[JobRow]
    skills: dict
    weights: dict
    index: dict
    years: dict
    years_src: dict
    roles: dict
    companies: dict
    clearance: dict
    fingerprint: tuple = ()
    built_at: float = 0.0


def _years(row) -> tuple[int | None, str]:
    bullets = row.requirements or []
    if (y := years_required(bullets)) is not None:
        return y, "requirements"
    if (y := years_from_title(row.title)) is not None:
        return y, "title"
    return years_from_pitch(bullets), "pitch"


def build_job_index(rows, fingerprint: tuple = ()) -> JobIndex:
    rows = [r for r in rows if r.skills]
    skills = {r.id: set(r.skills) for r in rows}
    years = {r.id: _years(r) for r in rows}
    return JobIndex(
        jobs=[JobRow(r.id, r.board, r.title, r.location) for r in rows],
        skills=skills,
        weights=idf_weights(list(skills.values())),
        index=build_index(skills),
        years={i: y for i, (y, _) in years.items()},
        years_src={i: src for i, (_, src) in years.items()},
        roles={r.id: (r.board, role_key(r.title)) for r in rows},
        companies={r.id: r.board for r in rows if r.board},
        clearance={r.id: needs_clearance(r.title, r.requirements or []) for r in rows},
        fingerprint=fingerprint,
        built_at=time.monotonic(),
    )


async def fresh_index(s: AsyncSession, fingerprint: tuple = ()) -> JobIndex:
    rows = (await s.execute(_ROWS)).all()
    return await asyncio.to_thread(build_job_index, rows, fingerprint)


async def _fingerprint(s: AsyncSession) -> tuple:
    ids_hash = func.coalesce(func.sum(func.hashtext(cast(Job.id, String))), 0)
    n, h = (await s.execute(select(func.count(), ids_hash).where(*OPEN))).one()
    return (n, int(h), default_tagger().version)


_cached: JobIndex | None = None


async def cached_index(s: AsyncSession) -> JobIndex:
    global _cached
    fp = await _fingerprint(s)
    idx = _cached
    if idx is None or idx.fingerprint != fp or time.monotonic() - idx.built_at > MAX_AGE_S:
        idx = _cached = await fresh_index(s, fp)
    return idx
