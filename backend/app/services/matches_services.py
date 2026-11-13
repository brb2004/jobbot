from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, Board, Job, MatchScore, Resume

SHOW = 20


def marked(user_id: UUID):
    return select(Application.job_id).where(Application.user_id == user_id)


async def for_user(s: AsyncSession, user_id: UUID, resume_id: UUID | None = None):
    if resume_id is None:
        resume_id = await s.scalar(
            select(Resume.id).where(Resume.user_id == user_id).order_by(Resume.created_at, Resume.id).limit(1)
        )
    stmt = (
        select(
            Job.id.label("job_id"),
            Job.title,
            MatchScore.score,
            Job.url,
            func.coalesce(Board.name, Job.board).label("company"),
            Job.location,
            MatchScore.detail,
        )
        .join(MatchScore, MatchScore.job_id == Job.id)
        .outerjoin(Board, Board.slug == Job.board)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id, Resume.id == resume_id)
        .where(Job.closed_at.is_(None))
        .where(Job.id.not_in(marked(user_id)))
        .order_by(MatchScore.score.desc(), Job.id)
        .limit(SHOW)
    )
    return (await s.execute(stmt)).all()
