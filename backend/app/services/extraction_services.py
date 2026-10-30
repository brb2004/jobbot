from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job
from app.llm.scorer_llm import LLMError


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