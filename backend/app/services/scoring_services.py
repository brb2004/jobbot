from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume, User
from app.llm.scorer_llm import LLMError
from app.services import extraction_services as extraction
from app.services import fit_services as fit
from app.services import prefilter_services as prefilter
from app.services.preferences_services import Preferences, allowed


async def score_new(s: AsyncSession, resume_extractor, fit_judge, k: int = 20, background=None) -> int:
    await extraction.extract_resume_skills(s, resume_extractor, background=background)   # AI, once per resume
    await extraction.fill_job_requirements(s)                                            # HTML parsing, no AI
    resumes = (await s.execute(select(Resume).where(Resume.skills.is_not(None)))).scalars().all()
    jobs = [j for j in (await s.execute(select(Job))).scalars().all() if j.requirements]
    already = set((await s.execute(select(MatchScore.resume_id, MatchScore.job_id))).all())

    users = {u.id: u for u in (await s.execute(select(User))).scalars().all()}

    def prefs_for(resume):
        user = users.get(resume.user_id)
        return Preferences.model_validate(user.preferences or {}) if user else Preferences()

    plan = []
    for r in resumes:
        prefs = prefs_for(r)
        candidates = [j for j in jobs if allowed(j, prefs)]          # user's filters, before any AI
        plan += [(r, j) for j in prefilter.top_k(r.raw_text or "", candidates, k) if (r.id, j.id) not in already]

    scored = 0
    for resume, job in plan:
        candidate = fit.profile_text(resume.skills, resume.education, resume.experience)
        try:
            result = await fit.judge_requirements(job.requirements, candidate, fit_judge)
        except LLMError:
            continue
        if result is None:
            continue
        s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=result.score,
                         detail={"met": result.met, "partial": result.partial,
                                 "missing": result.missing, "soft": result.soft}))
        await s.commit()
        scored += 1
    return scored
