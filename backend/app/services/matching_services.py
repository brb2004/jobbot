"""Glue between the database and the pure matcher in scoring_services."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume, User
from app.services.preferences_services import Preferences, allowed
from app.services.scoring_services import build_index, idf_weights, top_matches, years_required
from app.services.skills_services import default_tagger


async def tag_jobs(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    jobs = (await s.scalars(select(Job).where(Job.skills.is_(None), Job.requirements.is_not(None)))).all()
    for job in jobs:
        job.skills = sorted(set().union(*(tagger.tag(b) for b in job.requirements)))
    await s.commit()
    return len(jobs)


async def tag_resumes(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    resumes = (await s.scalars(select(Resume).where(Resume.skills.is_(None), Resume.raw_text.is_not(None)))).all()
    for r in resumes:
        r.skills = sorted(tagger.tag(r.raw_text))
    await s.commit()
    return len(resumes)


def _extra(prefs: Preferences) -> set[str]:
    """User-typed skills -> canonical names via the tagger ('k8s' -> 'Kubernetes'); unknown words drop out."""
    tagger = default_tagger()
    return set().union(*(tagger.tag(s) for s in prefs.extra_skills))


async def match_all(s: AsyncSession, k: int = 20) -> int:
    """Recompute every user's top k from scratch. Deterministic and cheap, so no caching needed."""
    tagger = default_tagger()
    jobs = [j for j in (await s.scalars(select(Job).where(Job.skills.is_not(None), Job.closed_at.is_(None)))).all()
            if j.skills]
    weights = idf_weights([set(j.skills) for j in jobs])                    # weights from ALL jobs
    years = {j.id: years_required(j.requirements or []) for j in jobs}
    all_jobs = {j.id: set(j.skills) for j in jobs}
    index = build_index(all_jobs)                                           # once per run, shared by every user
    users = {u.id: u for u in (await s.scalars(select(User))).all()}        # one query, not one per resume
    saved = 0
    for resume in (await s.scalars(select(Resume).where(Resume.skills.is_not(None)))).all():
        user = users.get(resume.user_id)
        prefs = Preferences.model_validate((user.preferences if user else None) or {})
        ok = {j.id for j in jobs if allowed(j, prefs)}                      # cheap + selective: filter first
        await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume.id))
        for m in top_matches(tagger.expand(set(resume.skills) | _extra(prefs)), all_jobs, weights, k,
                             index=index, within=ok, job_years=years, user_years=prefs.years_experience):
            s.add(MatchScore(resume_id=resume.id, job_id=m.job_id, score=m.score,
                             detail={"met": m.matched, "partial": [], "missing": m.missing, "soft": [],
                                     "years_asked": m.years_asked}))
            saved += 1
    await s.commit()                                                        # one commit for the whole run
    return saved
