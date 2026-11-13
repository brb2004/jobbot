from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, Board, Job, MatchScore, Resume

SHOW = 20  # matches on the dashboard; more are stored as a reserve (matching_services.RESERVE)


def marked(user_id: UUID):
    """Jobs this user applied to or dismissed: never shown as matches."""
    return select(Application.job_id).where(Application.user_id == user_id)


async def for_user(s: AsyncSession, user_id: UUID, resume_id: UUID | None = None):
    """One resume's matches: the given one (if it's theirs), else their first. Applied/dismissed are per account."""
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
        .outerjoin(Board, Board.slug == Job.board)  # real name when we have it
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id, Resume.id == resume_id)
        .where(Job.closed_at.is_(None))  # closed since the last match run: gone now
        .where(Job.id.not_in(marked(user_id)))  # applied / dismissed: the next one moves up
        .order_by(MatchScore.score.desc(), Job.id)
        .limit(SHOW)
    )
    return (await s.execute(stmt)).all()
