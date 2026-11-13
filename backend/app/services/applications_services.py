from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, Board, Job


async def mark(s: AsyncSession, user_id: UUID, job_id: UUID, status: str = "applied") -> bool:
    if await s.get(Job, job_id) is None:
        return False
    stmt = insert(Application).values(user_id=user_id, job_id=job_id, status=status)
    await s.execute(
        stmt.on_conflict_do_update(
            constraint="uq_applications_user_job", set_={"status": stmt.excluded.status}
        )
    )
    await s.commit()
    return True


async def undo(s: AsyncSession, user_id: UUID, job_id: UUID) -> None:
    await s.execute(delete(Application).where(Application.user_id == user_id, Application.job_id == job_id))
    await s.commit()


async def list_for(s: AsyncSession, user_id: UUID) -> list[dict]:
    rows = (
        await s.execute(
            select(
                Job.id,
                Job.title,
                func.coalesce(Board.name, Job.board).label("company"),
                Job.location,
                Job.url,
                Job.closed_at,
                Application.created_at,
            )
            .join(Application, Application.job_id == Job.id)
            .outerjoin(Board, Board.slug == Job.board)
            .where(Application.user_id == user_id, Application.status == "applied")
            .order_by(Application.created_at.desc())
        )
    ).all()
    return [
        {
            "job_id": r.id,
            "title": r.title,
            "company": r.company,
            "location": r.location,
            "url": r.url,
            "closed": r.closed_at is not None,
            "applied_at": r.created_at,
        }
        for r in rows
    ]
