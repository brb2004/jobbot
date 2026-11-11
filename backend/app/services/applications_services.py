"""Applied jobs leave the matches list; matching re-runs for that user so the next match moves up."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, Job


async def _rematch(s: AsyncSession, user_id: UUID) -> None:
    from app.services.matching_services import match_all          # local import: matching imports a lot
    await match_all(s, user_id=user_id)


async def mark(s: AsyncSession, user_id: UUID, job_id: UUID) -> bool:
    if await s.get(Job, job_id) is None:
        return False
    await s.execute(insert(Application).values(user_id=user_id, job_id=job_id, status="applied")
                    .on_conflict_do_nothing(constraint="uq_applications_user_job"))   # idempotent
    await s.commit()
    await _rematch(s, user_id)
    return True


async def undo(s: AsyncSession, user_id: UUID, job_id: UUID) -> None:
    await s.execute(delete(Application).where(Application.user_id == user_id, Application.job_id == job_id))
    await s.commit()
    await _rematch(s, user_id)


async def list_for(s: AsyncSession, user_id: UUID) -> list[dict]:
    rows = (await s.execute(
        select(Job.id, Job.title, Job.board, Job.location, Job.url, Job.closed_at, Application.created_at)
        .join(Application, Application.job_id == Job.id)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc()))).all()
    return [{"job_id": r.id, "title": r.title, "company": r.board, "location": r.location, "url": r.url,
             "closed": r.closed_at is not None, "applied_at": r.created_at} for r in rows]
