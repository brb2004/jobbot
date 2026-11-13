from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.batches_db import batches
from app.db.models_db import Job, Resume
from app.services.skills_services import default_tagger


def _stale(model, tagger):
    return or_(model.skills_version.is_(None), model.skills_version != tagger.version)


async def tag_jobs(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    done = 0
    stmt = select(Job).where(Job.requirements.is_not(None), _stale(Job, tagger))
    async for jobs in batches(s, stmt, Job.id):
        for job in jobs:
            job.skills = sorted(set().union(*(tagger.tag(b) for b in job.requirements)))
            job.skills_version = tagger.version
        await s.commit()
        done += len(jobs)
    return done


async def tag_resumes(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    stmt = select(Resume).where(Resume.raw_text.is_not(None), _stale(Resume, tagger))
    resumes = (await s.scalars(stmt)).all()
    for r in resumes:
        r.skills = sorted(tagger.tag(r.raw_text))
        r.skills_version = tagger.version
    await s.commit()
    return len(resumes)
