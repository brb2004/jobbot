import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import DigestSent, Job, MatchScore, Resume, User
from app.schemas.matches_schemas import MatchOut
from app.services.digest_render_services import groups, render
from app.services.matches_services import marked
from app.services.scoring_services import TIERS, tier  # noqa: F401
from app.services.seen_services import mark_seen, seen_ids

log = logging.getLogger(__name__)


async def matches_for(s: AsyncSession, user_id: UUID) -> list[MatchOut]:
    stmt = (
        select(Job.id.label("job_id"), Job.title, MatchScore.score, Job.url, MatchScore.detail,
               Resume.name.label("resume"))
        .join(MatchScore, MatchScore.job_id == Job.id)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id, Job.closed_at.is_(None), Job.id.not_in(marked(user_id)))
        .order_by(MatchScore.score.desc())
    )  # fmt: skip
    return [MatchOut.model_validate(r, from_attributes=True) for r in (await s.execute(stmt)).all()]


async def _recipients(s: AsyncSession, week: str) -> list[UUID]:
    skip = exists().where(
        User.id == Resume.user_id, User.email_verified_at.is_(None) | User.digest_opt_out_at.is_not(None)
    )
    users = (await s.execute(select(Resume.user_id).distinct().where(~skip))).scalars().all()
    done = set((await s.scalars(select(DigestSent.user_id).where(DigestSent.week == week))).all())
    return [u for u in users if u not in done]


async def _send_one(s: AsyncSession, sender, user_id: UUID, week: str, top_n: int) -> bool:
    matches = await matches_for(s, user_id)
    seen = await seen_ids(s, user_id, (m.job_id for m in matches))
    new = [m for m in matches if m.job_id not in seen]
    if not new:
        return False
    still = [m for m in matches if m.job_id in seen]
    s.add(DigestSent(user_id=user_id, week=week))
    await s.commit()
    try:
        await sender.send(user_id, render(new, top_n, still))
    except Exception:
        log.exception("weekly digest to %s failed", user_id)
        await s.execute(delete(DigestSent).where(DigestSent.user_id == user_id, DigestSent.week == week))
        await s.commit()
        return False
    await mark_seen(s, user_id, [m.job_id for _, ms in groups(new, top_n) for m in ms])
    await s.commit()
    return True


async def send_weekly(s: AsyncSession, sender, now: datetime, top_n: int = 20) -> int:
    year, wk, _ = now.isocalendar()
    week = f"{year}-W{wk:02d}"
    sent = 0
    for user_id in await _recipients(s, week):
        sent += await _send_one(s, sender, user_id, week, top_n)
    return sent
