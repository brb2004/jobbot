from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job
from app.llm.scorer_llm import LLMError
from app.db.models_db import Resume


async def extract_job_requirements(s: AsyncSession, extractor) -> int:
    stmt = select(Job).where(Job.requirements.is_(None), Job.description.is_not(None))
    jobs = (await s.execute(stmt)).scalars().all()

    done = 0
    for job in jobs:
        try:
            job.requirements = await extractor.extract(job.description)
        except LLMError:
            continue                 # stays NULL -> retried next run
        await s.commit()             # commit each job: a crash at job 3,000 keeps the first 2,999
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