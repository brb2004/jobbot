from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume
from app.llm.scorer_llm import LLMError
from app.services import prefilter_services as prefilter


async def score_new(s: AsyncSession, llm, k: int = 20) -> int:
    resumes = (await s.execute(select(Resume))).scalars().all()
    jobs = list((await s.execute(select(Job))).scalars().all())
    already = set((await s.execute(select(MatchScore.resume_id, MatchScore.job_id))).all())

    scored = 0
    for resume in resumes:
        for job in prefilter.top_k(resume.raw_text or "", jobs, k):
            if (resume.id, job.id) in already:
                continue
            try:
                score = await llm.score(resume, job)
            except LLMError:
                continue                          # no row saved → retried next run
            s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=score))
            scored += 1
    await s.commit()
    return scored