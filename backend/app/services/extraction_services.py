from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.batches_db import batches
from app.db.models_db import Job
from app.ingest.sections_ingest import requirement_bullets


async def fill_job_requirements(s: AsyncSession, job_ids=None) -> int:
    stmt = select(Job).where(Job.requirements.is_(None), Job.content_html.is_not(None))
    if job_ids is not None:
        if not job_ids:
            return 0
        stmt = stmt.where(Job.id.in_(job_ids))
    done = 0
    async for jobs in batches(s, stmt, Job.id):
        for job in jobs:
            job.requirements = requirement_bullets(job.content_html)
        await s.commit()
        done += len(jobs)
    return done
