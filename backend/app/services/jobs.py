from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Job
from sqlalchemy import select
async def get(s: AsyncSession, job_id: UUID) -> Job | None:
    return await s.get(Job, job_id)

async def list_all(s: AsyncSession) -> list[Job]:
    result = await s.execute(select(Job))
    return list(result.scalars().all())