from sqlalchemy import case, literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job

BATCH = 1000


def deferred_upsert(rows: list[dict]):
    stmt = insert(Job).values(rows)
    edited = Job.source_updated_at.is_not(None) & Job.source_updated_at.is_distinct_from(
        stmt.excluded.source_updated_at
    )
    return stmt.on_conflict_do_update(
        constraint="uq_jobs_board_external",
        set_={
            "title": stmt.excluded.title,
            "url": stmt.excluded.url,
            "location": stmt.excluded.location,
            "description": case((edited, None), else_=Job.description),
            "source_updated_at": stmt.excluded.source_updated_at,
            "closed_at": None,
        },
    )


def inline_upsert(rows: list[dict]):
    stmt = insert(Job).values(rows)
    x = stmt.excluded
    changed = Job.source_updated_at.is_distinct_from(x.source_updated_at) | Job.content_html.is_(None)
    fresh = {
        c: case((changed, getattr(x, c)), else_=getattr(Job, c))
        for c in ("content_html", "description", "salary_min", "salary_max", "salary_currency")
    }
    return stmt.on_conflict_do_update(
        constraint="uq_jobs_board_external",
        set_={
            "title": x.title,
            "url": x.url,
            "location": x.location,
            **fresh,
            "requirements": case((changed, None), else_=Job.requirements),
            "skills_version": case((changed, None), else_=Job.skills_version),
            "source_updated_at": x.source_updated_at,
            "closed_at": None,
        },
    )


async def upsert(s: AsyncSession, build, rows: list[dict]) -> int:
    new = 0
    for i in range(0, len(rows), BATCH):
        stmt = build(rows[i : i + BATCH]).returning(literal_column("xmax = 0"))
        new += sum((await s.execute(stmt)).scalars().all())
    return new
