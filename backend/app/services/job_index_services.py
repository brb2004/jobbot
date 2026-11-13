"""Everything matching derives from the open jobs, built once and shared by every user's rematch."""

import asyncio
import time
from dataclasses import dataclass

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job
from app.services.requirements_services import needs_clearance, years_from_title, years_required
from app.services.scoring_services import build_index, idf_weights
from app.services.skills_services import default_tagger
from app.services.titles_services import role_key

MAX_AGE_S = 3600  # requirements re-extracted in place don't change the fingerprint, so rebuild hourly too
OPEN = (Job.skills.is_not(None), Job.closed_at.is_(None))
# Only the columns matching needs: leaving out the posting text is ~100 MB less per load.
_ROWS = select(Job.id, Job.board, Job.title, Job.location, Job.skills, Job.requirements).where(*OPEN)


@dataclass(frozen=True)
class JobRow:
    """What the preference filter reads about a job."""

    id: object
    board: str | None
    title: str | None
    location: str | None


@dataclass(frozen=True)
class JobIndex:
    jobs: list[JobRow]
    skills: dict  # job id -> skills
    weights: dict  # skill -> IDF weight
    index: dict  # skill -> job ids
    years: dict  # job id -> years asked: stated, else implied by the title
    years_src: dict  # job id -> "requirements" | "title"
    roles: dict  # job id -> (company, role): one posting per role
    companies: dict  # job id -> company
    clearance: dict  # job id -> may need clearance or citizenship
    fingerprint: tuple = ()
    built_at: float = 0.0


def build_job_index(rows, fingerprint: tuple = ()) -> JobIndex:
    """Pure CPU, no database, so it can run in a worker thread."""
    rows = [r for r in rows if r.skills]
    skills = {r.id: set(r.skills) for r in rows}
    stated = {r.id: years_required(r.requirements or []) for r in rows}
    return JobIndex(
        jobs=[JobRow(r.id, r.board, r.title, r.location) for r in rows],
        skills=skills,
        weights=idf_weights(list(skills.values())),
        index=build_index(skills),
        years={r.id: stated[r.id] if stated[r.id] is not None else years_from_title(r.title) for r in rows},
        years_src={r.id: "requirements" if stated[r.id] is not None else "title" for r in rows},
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
    """Changes when any job opens, closes or gets tagged, or skills.txt changes. Milliseconds to compute."""
    ids_hash = func.coalesce(func.sum(func.hashtext(cast(Job.id, String))), 0)
    n, h = (await s.execute(select(func.count(), ids_hash).where(*OPEN))).one()
    return (n, int(h), default_tagger().version)


_cached: JobIndex | None = None


async def cached_index(s: AsyncSession) -> JobIndex:
    """The process-wide index, rebuilt only when the open jobs changed."""
    global _cached
    fp = await _fingerprint(s)
    idx = _cached
    if idx is None or idx.fingerprint != fp or time.monotonic() - idx.built_at > MAX_AGE_S:
        idx = _cached = await fresh_index(s, fp)
    return idx
