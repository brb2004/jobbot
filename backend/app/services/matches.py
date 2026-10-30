from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Job, Resume, MatchScore

async def for_user(s: AsyncSession, user_id: UUID):
    stmt = (
        select(Job.id.label("job_id"), Job.title, MatchScore.score)
        .join(MatchScore, MatchScore.job_id == Job.id)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id)          # only mine
        .order_by(MatchScore.score.desc())         # best first
    )
    return (await s.execute(stmt)).all()