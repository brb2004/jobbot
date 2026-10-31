from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models_db import Job, Resume, MatchScore
from app.schemas.matches_schemas import MatchOut


def render(matches: list[MatchOut], top_n: int) -> str:
    if not matches:
        return "No new matches this week."

    best = sorted(matches, key=lambda m: m.score, reverse=True)[:top_n]
    lines = [f"{i}. {m.title} — {round(m.score * 100)}% match" for i, m in enumerate(best, 1)]
    return "Your top matches this week:\n\n" + "\n".join(lines)


async def matches_for(s: AsyncSession, user_id: UUID, since: datetime):
    stmt = (
        select(Job.id.label("job_id"), Job.title, MatchScore.score)
        .join(MatchScore, MatchScore.job_id == Job.id)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id)
        .where(MatchScore.scored_at >= since)
        .order_by(MatchScore.score.desc())
    )
    return (await s.execute(stmt)).all()


async def send_weekly(s: AsyncSession, sender, now: datetime, top_n: int = 5) -> int:
    since = now - timedelta(days=7)
    user_ids = (await s.execute(select(Resume.user_id).distinct())).scalars().all()

    sent = 0
    for user_id in user_ids:
        matches = await matches_for(s, user_id, since)
        if not matches:
            continue                      # rule: no new matches → no email
        await sender.send(user_id, render(matches, top_n))
        sent += 1
    return sent