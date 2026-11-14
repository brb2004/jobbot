import asyncio
import time
from dataclasses import dataclass, field

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job
from app.services.locations_services import scoped_location
from app.services.pay_level_services import years_from_pay
from app.services.requirements_services import (
    experienced_pitch,
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
_ROWS = select(
    Job.id,
    Job.board,
    Job.title,
    Job.location,
    Job.skills,
    Job.requirements,
    Job.salary_min,
    Job.salary_currency,
    Job.degree,
).where(*OPEN)


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
    core: dict = field(default_factory=dict)
    pay: dict = field(default_factory=dict)
    degree: dict = field(default_factory=dict)
    fingerprint: tuple = ()
    built_at: float = 0.0


def _years(row) -> tuple[int | None, str]:
    bullets = row.requirements or []
    found = (
        ("requirements", lambda: years_required(bullets)),
        ("title", lambda: years_from_title(row.title)),
        ("pitch", lambda: years_from_pitch(bullets)),
        ("experienced", lambda: experienced_pitch(bullets)),
        (
            "pay",
            lambda: years_from_pay(
                row.title, getattr(row, "salary_min", None), getattr(row, "salary_currency", None)
            ),
        ),
    )
    return next(((y, src) for src, fn in found if (y := fn()) is not None), (None, "title"))


def _title_skills(rows) -> dict:
    tagger = default_tagger()
    by_title = {t: frozenset(tagger.tag(t)) for t in {r.title or "" for r in rows}}
    return {r.id: by_title[r.title or ""] for r in rows if by_title[r.title or ""]}


SOFT = frozenset({"pay", "experienced"})


def soft_years(idx) -> set:
    return {j for j, src in idx.years_src.items() if src in SOFT}


def build_job_index(rows, fingerprint: tuple = ()) -> JobIndex:
    rows = [r for r in rows if r.skills]
    skills = {r.id: set(r.skills) for r in rows}
    years = {r.id: _years(r) for r in rows}
    return JobIndex(
        jobs=[JobRow(r.id, r.board, r.title, scoped_location(r.title, r.location)) for r in rows],
        skills=skills,
        weights=idf_weights(list(skills.values())),
        index=build_index(skills),
        years={i: y for i, (y, _) in years.items()},
        years_src={i: src for i, (_, src) in years.items()},
        roles={r.id: (r.board, role_key(r.title)) for r in rows},
        companies={r.id: r.board for r in rows if r.board},
        clearance={r.id: needs_clearance(r.title, r.requirements or []) for r in rows},
        core=_title_skills(rows),
        pay={r.id: int(r.salary_min) for r in rows if years[r.id][1] == "pay"},
        degree={r.id: r.degree for r in rows if getattr(r, "degree", None)},
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
