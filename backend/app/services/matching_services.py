"""Glue between the database and the pure matcher in scoring_services."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume, User
from app.services.preferences_services import Preferences, allowed
from app.services.scoring_services import idf_weights, top_matches, years_required
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


async def match_all(s: AsyncSession, k: int = 20) -> int:
    """Recompute every user's top k from scratch. Deterministic and cheap, so no caching needed."""
    jobs = [j for j in (await s.scalars(select(Job).where(Job.skills.is_not(None)))).all() if j.skills]
    weights = idf_weights([set(j.skills) for j in jobs])                    # weights from ALL jobs
    years = {j.id: years_required(j.requirements or []) for j in jobs}
    saved = 0
    for resume in (await s.scalars(select(Resume).where(Resume.skills.is_not(None)))).all():
        user = await s.get(User, resume.user_id)
        prefs = Preferences.model_validate((user.preferences if user else None) or {})
        pool = {j.id: set(j.skills) for j in jobs if allowed(j, prefs)}
        await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume.id))
        for m in top_matches(default_tagger().expand(set(resume.skills)), pool, weights, k,
                             job_years=years, user_years=prefs.years_experience):
            s.add(MatchScore(resume_id=resume.id, job_id=m.job_id, score=m.score,
                             detail={"met": m.matched, "partial": [], "missing": m.missing, "soft": [],
                                     "years_asked": m.years_asked}))
            saved += 1
        await s.commit()
    return saved
