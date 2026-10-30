from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Job

async def get(s: AsyncSession, job_id: UUID) -> Job | None:
    return await s.get(Job, job_id)