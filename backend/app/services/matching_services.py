"""Glue between the database and the pure matcher in scoring_services."""
import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.batches_db import batches
from app.db.models_db import Application, Job, MatchScore, Resume, User
from app.services.preferences_services import Preferences, allowed
from app.services.scoring_services import build_index, idf_weights, needs_clearance, top_matches, years_from_title, years_required
from app.services.skills_services import default_tagger
from app.services.titles_services import role_key


PER_COMPANY = 2          # at most 2 of anyone's top k from one company
RESERVE = 20             # extra matches stored past the k shown: apply / dismiss just reveal the next one
LOCK_NS = 7342           # advisory-lock namespace for per-resume rematches


def _stale(model, tagger):
    """Never tagged, or tagged with a different skills.txt."""
    return or_(model.skills_version.is_(None), model.skills_version != tagger.version)


async def tag_jobs(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    done = 0
    async for jobs in batches(s, select(Job).where(Job.requirements.is_not(None), _stale(Job, tagger)), Job.id):
        for job in jobs:
            job.skills = sorted(set().union(*(tagger.tag(b) for b in job.requirements)))
            job.skills_version = tagger.version
        await s.commit()
        done += len(jobs)
    return done


async def tag_resumes(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    resumes = (await s.scalars(select(Resume).where(Resume.raw_text.is_not(None), _stale(Resume, tagger)))).all()
    for r in resumes:
        r.skills = sorted(tagger.tag(r.raw_text))
        r.skills_version = tagger.version
    await s.commit()
    return len(resumes)


def _extra(prefs: Preferences) -> set[str]:
    """User-typed skills -> canonical names via the tagger ('k8s' -> 'Kubernetes'); unknown words drop out."""
    tagger = default_tagger()
    return set().union(*(tagger.tag(s) for s in prefs.extra_skills))


@dataclass(frozen=True)
class JobRow:
    """What filtering needs about a job (allowed() reads title and location)."""
    id: object
    board: str | None
    title: str | None
    location: str | None


@dataclass(frozen=True)
class JobIndex:
    """Everything matching derives from the open jobs, built once and shared by every user's rematch."""
    jobs: list[JobRow]
    skills: dict          # job id -> set of skills
    weights: dict         # skill -> IDF weight
    index: dict           # skill -> job ids (inverted index)
    years: dict           # job id -> years asked (stated, else from the title)
    years_src: dict       # job id -> "requirements" | "title"
    roles: dict           # job id -> (company, role key): one posting per role
    companies: dict       # job id -> company: PER_COMPANY cap
    clearance: dict       # job id -> may need clearance / citizenship
    fingerprint: tuple = ()
    built_at: float = 0.0


def build_job_index(rows, fingerprint: tuple = ()) -> JobIndex:
    """Pure CPU, no database: runs in a worker thread so the API's event loop keeps serving other requests."""
    rows = [r for r in rows if r.skills]
    skills = {r.id: set(r.skills) for r in rows}
    years, years_src = {}, {}
    for r in rows:                                                          # stated number first, then the title
        stated = years_required(r.requirements or [])
        years[r.id] = stated if stated is not None else years_from_title(r.title)
        years_src[r.id] = "requirements" if stated is not None else "title"
    return JobIndex(
        jobs=[JobRow(r.id, r.board, r.title, r.location) for r in rows],
        skills=skills,
        weights=idf_weights(list(skills.values())),                         # weights from ALL open jobs
        index=build_index(skills),
        years=years, years_src=years_src,
        roles={r.id: (r.board, role_key(r.title)) for r in rows},
        companies={r.id: r.board for r in rows if r.board},
        clearance={r.id: needs_clearance(r.title, r.requirements or []) for r in rows},
        fingerprint=fingerprint, built_at=time.monotonic())


# only the columns matching needs: skipping content_html/description is ~100 MB less per load
_OPEN = (select(Job.id, Job.board, Job.title, Job.location, Job.skills, Job.requirements)
         .where(Job.skills.is_not(None), Job.closed_at.is_(None)))


async def fresh_index(s: AsyncSession, fingerprint: tuple = ()) -> JobIndex:
    rows = (await s.execute(_OPEN)).all()
    return await asyncio.to_thread(build_job_index, rows, fingerprint)


async def _fingerprint(s: AsyncSession) -> tuple:
    """Changes whenever the set of open, tagged jobs changes (any job opens, closes or gets tagged) or skills.txt
    does. One indexed aggregate: milliseconds, versus seconds to rebuild."""
    n, h = (await s.execute(select(func.count(), func.coalesce(func.sum(func.hashtext(cast(Job.id, String))), 0))
                            .where(Job.skills.is_not(None), Job.closed_at.is_(None)))).one()
    return (n, int(h), default_tagger().version)


_cached: JobIndex | None = None
MAX_AGE_S = 3600          # rebuild at least hourly anyway (requirements re-extracted in place don't move the fingerprint)


async def cached_index(s: AsyncSession) -> JobIndex:
    """The process-wide index, rebuilt only when the open jobs changed. Uploads and preference saves use it."""
    global _cached
    fp = await _fingerprint(s)
    idx = _cached
    if idx is None or idx.fingerprint != fp or time.monotonic() - idx.built_at > MAX_AGE_S:
        idx = _cached = await fresh_index(s, fp)
    return idx


def _pick(idx: JobIndex, user_skills: set[str], prefs: Preferences, store: int, user_years):
    ok = {j.id for j in idx.jobs if allowed(j, prefs)}                      # cheap + selective: filter first
    return top_matches(user_skills, idx.skills, idx.weights, store, index=idx.index, within=ok,
                       dedupe_key=idx.roles, company=idx.companies, per_company=PER_COMPANY,
                       job_years=idx.years, user_years=user_years)


async def match_all(s: AsyncSession, k: int = 20, user_id: UUID | None = None,
                    index: JobIndex | None = None) -> int:
    """Recompute each user's top matches from scratch: k shown, plus RESERVE and the jobs they applied to or
    dismissed (the dashboard hides those), so marking a job never needs a rematch and undo always brings it back.
    Each resume is locked and committed on its own: two rematches of one user wait for each other instead of
    colliding on the unique (resume, job) key, and the nightly run never holds every user's rows at once.
    The scoring runs in a worker thread; only the database work stays on the event loop."""
    idx = index or await fresh_index(s)
    tagger = default_tagger()
    users_q, applied_q = select(User), select(Application.user_id, Application.job_id)
    resumes = select(Resume).where(Resume.skills.is_not(None))
    if user_id is not None:                                                 # just this user
        users_q = users_q.where(User.id == user_id)
        applied_q = applied_q.where(Application.user_id == user_id)
        resumes = resumes.where(Resume.user_id == user_id)
    users = {u.id: u for u in (await s.scalars(users_q)).all()}             # one query, not one per resume
    applied: dict = {}                                                      # applied / dismissed: hidden on read
    for uid, jid in (await s.execute(applied_q)).all():
        applied.setdefault(uid, set()).add(jid)
    saved = 0
    for resume in (await s.scalars(resumes)).all():
        user = users.get(resume.user_id)
        prefs = Preferences.model_validate((user.preferences if user else None) or {})
        store = k + RESERVE + len(applied.get(resume.user_id, ()))
        mine = tagger.expand(set(resume.skills) | _extra(prefs))
        user_years = prefs.years_experience if prefs.years_experience is not None else resume.years_detected
        picks = await asyncio.to_thread(_pick, idx, mine, prefs, store, user_years)
        await s.execute(select(func.pg_advisory_xact_lock(LOCK_NS, func.hashtext(str(resume.id)))))
        await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume.id))
        for m in picks:
            s.add(MatchScore(resume_id=resume.id, job_id=m.job_id, score=m.score,
                             detail={"met": m.matched, "partial": [], "missing": m.missing, "soft": [],
                                     "years_asked": m.years_asked,
                                     "years_source": idx.years_src.get(m.job_id), "over_years": m.over_years,
                                     "no_language": m.no_language,
                                     "clearance": idx.clearance.get(m.job_id, False)}))
            saved += 1
        await s.commit()                                                    # per user: releases the lock
    return saved


async def rematch_user(s: AsyncSession, user_id: UUID) -> int:
    """After an upload or a preferences save: one user against the shared cached index, off the event loop."""
    return await match_all(s, user_id=user_id, index=await cached_index(s))
