import asyncio
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, MatchScore, Resume, User
from app.services import job_index_services
from app.services.job_index_services import JobIndex, fresh_index
from app.services.preferences_services import Preferences, allowed, for_resume
from app.services.scoring_services import top_matches
from app.services.skills_services import default_tagger

PER_COMPANY = 2
RESERVE = 20
LOCK_NS = 7342


async def match_all(
    s: AsyncSession, k: int = 20, user_id: UUID | None = None, index: JobIndex | None = None
) -> int:
    idx = index or await fresh_index(s)
    users, marked = await _users_and_marks(s, user_id)
    resumes = select(Resume).where(Resume.skills.is_not(None))
    if user_id is not None:
        resumes = resumes.where(Resume.user_id == user_id)
    saved = 0
    for resume in (await s.scalars(resumes)).all():
        user = users.get(resume.user_id)
        prefs = for_resume(
            Preferences.model_validate((user.preferences if user else None) or {}), resume.title_prefs
        )
        picks = await asyncio.to_thread(
            _pick, idx, resume, prefs, k + RESERVE + marked.get(resume.user_id, 0)
        )
        saved += await _replace_scores(s, idx, resume.id, picks)
    return saved


async def rematch_user(s: AsyncSession, user_id: UUID) -> int:
    return await match_all(s, user_id=user_id, index=await job_index_services.cached_index(s))


async def _users_and_marks(s: AsyncSession, user_id: UUID | None) -> tuple[dict, dict]:
    users_q = select(User)
    marks_q = select(Application.user_id, func.count()).group_by(Application.user_id)
    if user_id is not None:
        users_q, marks_q = users_q.where(User.id == user_id), marks_q.where(Application.user_id == user_id)
    users = {u.id: u for u in (await s.scalars(users_q)).all()}
    return users, dict((await s.execute(marks_q)).all())


def _pick(idx: JobIndex, resume: Resume, prefs: Preferences, store: int):
    tagger = default_tagger()
    typed = set().union(*(tagger.tag(word) for word in prefs.extra_skills))
    mine = tagger.expand(set(resume.skills) | typed)
    years = prefs.years_experience if prefs.years_experience is not None else resume.years_detected
    ok = {j.id for j in idx.jobs if allowed(j, prefs)}
    return top_matches(mine, idx.skills, idx.weights, store, index=idx.index, within=ok, dedupe_key=idx.roles,
                       company=idx.companies, per_company=PER_COMPANY, job_years=idx.years, user_years=years)  # fmt: skip


async def _replace_scores(s: AsyncSession, idx: JobIndex, resume_id, picks) -> int:
    await s.execute(select(func.pg_advisory_xact_lock(LOCK_NS, func.hashtext(str(resume_id)))))
    await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume_id))
    s.add_all(
        MatchScore(resume_id=resume_id, job_id=m.job_id, score=m.score, detail=_detail(idx, m)) for m in picks
    )
    await s.commit()
    return len(picks)


def _detail(idx: JobIndex, m) -> dict:
    return {"met": m.matched, "partial": [], "missing": m.missing, "soft": [], "years_asked": m.years_asked,
            "years_source": idx.years_src.get(m.job_id), "over_years": m.over_years,
            "no_language": m.no_language, "clearance": idx.clearance.get(m.job_id, False)}  # fmt: skip
