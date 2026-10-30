from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, Resume
from app.llm.scorer_llm import LLMError


async def extract_job_requirements(s: AsyncSession, extractor, job_ids=None) -> int:
    stmt = select(Job).where(Job.requirements.is_(None), Job.description.is_not(None))
    if job_ids is not None:
        if not job_ids:
            return 0
        stmt = stmt.where(Job.id.in_(job_ids))          # only the jobs someone actually needs
    jobs = (await s.execute(stmt)).scalars().all()

    done = 0
    for job in jobs:
        try:
            job.requirements = await extractor.extract(job.description)
        except LLMError:
            continue
        await s.commit()
        done += 1
    return done


async def extract_resume_skills(s: AsyncSession, extractor) -> int:
    stmt = select(Resume).where(Resume.skills.is_(None), Resume.raw_text.is_not(None))
    resumes = (await s.execute(stmt)).scalars().all()

    done = 0
    for resume in resumes:
        try:
            resume.skills = await extractor.extract(resume.raw_text)
        except LLMError:
            continue
        await s.commit()
        done += 1
    return done
