"""Keep the database from only growing. Closed postings lose their big text after CLEAR_AFTER and the
row itself after DELETE_AFTER, unless someone applied to it or dismissed it (their Applied tab keeps it).
Their match scores go with them (ON DELETE CASCADE, indexed on job_id)."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Application, Job

CLEAR_AFTER = timedelta(days=30)
DELETE_AFTER = timedelta(days=90)


@dataclass
class Pruned:
    cleared: int
    deleted: int


async def prune(s: AsyncSession, now: datetime | None = None) -> Pruned:
    now = now or datetime.now(timezone.utc)
    cleared = (await s.execute(
        update(Job)
        .where(Job.closed_at < now - CLEAR_AFTER, Job.content_html.is_not(None))
        .values(content_html=None, description=None)            # reopened later -> fetched again
    )).rowcount
    deleted = (await s.execute(
        delete(Job)
        .where(Job.closed_at < now - DELETE_AFTER, ~exists().where(Application.job_id == Job.id))
    )).rowcount
    await s.commit()
    return Pruned(cleared, deleted)
