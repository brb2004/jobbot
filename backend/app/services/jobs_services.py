from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job


async def get(s: AsyncSession, job_id: UUID) -> Job | None:
    return await s.get(Job, job_id)


async def list_open(s: AsyncSession, limit: int, offset: int) -> list[Job]:
    stmt = select(Job).where(Job.closed_at.is_(None)).order_by(Job.id).limit(limit).offset(offset)
    return list((await s.execute(stmt)).scalars().all())
