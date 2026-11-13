from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import SeenJob


async def seen_ids(s: AsyncSession, user_id: UUID, job_ids) -> set:
    job_ids = list(job_ids)
    if not job_ids:
        return set()
    stmt = select(SeenJob.job_id).where(SeenJob.user_id == user_id, SeenJob.job_id.in_(job_ids))
    return set((await s.scalars(stmt)).all())


async def mark_seen(s: AsyncSession, user_id: UUID, job_ids) -> None:
    rows = [{"user_id": user_id, "job_id": j} for j in dict.fromkeys(job_ids)]
    if rows:
        await s.execute(insert(SeenJob).values(rows).on_conflict_do_nothing())
