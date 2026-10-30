from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume
from app.llm.scorer_llm import LLMError
from app.services import extraction_services as extraction
from app.services import fit_services as fit
from app.services import prefilter_services as prefilter


async def score_new(s: AsyncSession, resume_extractor, fit_judge, k: int = 20) -> int:
    await extraction.extract_resume_skills(s, resume_extractor)          # AI, once per resume
    await extraction.fill_job_requirements(s)                            # HTML parsing, no AI
    resumes = (await s.execute(select(Resume).where(Resume.skills.is_not(None)))).scalars().all()
    jobs = [j for j in (await s.execute(select(Job))).scalars().all() if j.requirements]
    already = set((await s.execute(select(MatchScore.resume_id, MatchScore.job_id))).all())

    plan = [(r, j) for r in resumes
            for j in prefilter.top_k(r.raw_text or "", jobs, k)
            if (r.id, j.id) not in already]

    scored = 0
    for resume, job in plan:
        try:
            result = await fit.judge_requirements(job.requirements, resume.skills, fit_judge)
        except LLMError:
            continue                                                     # not saved: retried next run
        if result is None:
            continue
        s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=result.score,
                         detail={"met": result.met, "partial": result.partial, "missing": result.missing}))
        await s.commit()                                                 # save each pair: long runs keep progress
        scored += 1
    return scored
