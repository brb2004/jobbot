from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume
from app.schemas.matches_schemas import MatchOut

SHOW = 3          # requirements shown per list
WIDTH = 80        # characters per requirement before trimming
# Cutoffs tuned to the matcher's smoothing prior (realistic top ~0.5). Revisit after a few weeks of data.
TIERS = [(0.45, "Strong match"), (0.30, "Worth applying"), (0.0, "Stretch")]


def tier(score: float) -> str:
    return next(label for cut, label in TIERS if score >= cut)


def _short(items: list[str]) -> str:
    trimmed = [i if len(i) <= WIDTH else i[:WIDTH - 1].rstrip() + "…" for i in items[:SHOW]]
    more = f" (+{len(items) - SHOW} more)" if len(items) > SHOW else ""
    return "; ".join(trimmed) + more


def render(matches: list[MatchOut], top_n: int) -> str:
    if not matches:
        return "No new matches this week."

    best = sorted(matches, key=lambda m: m.score, reverse=True)[:top_n]
    blocks = []
    for i, m in enumerate(best, 1):
        d = m.detail or {}
        head = f"{i}. {m.title} — {tier(m.score)}"
        if d.get("years_asked"):
            head += f" · asks for {d['years_asked']}+ years"
        lines = [head]
        if d.get("met"):
            lines.append(f"   You have: {_short(d['met'])}")
        if d.get("partial"):
            lines.append(f"   Partly:   {_short(d['partial'])}")
        if d.get("missing"):
            lines.append(f"   Missing:  {_short(d['missing'])}")
        if m.url:
            lines.append(f"   {m.url}")
        blocks.append("\n".join(lines))
    return "Your top matches this week:\n\n" + "\n\n".join(blocks)


async def matches_for(s: AsyncSession, user_id: UUID, since: datetime):
    stmt = (
        select(Job.id.label("job_id"), Job.title, MatchScore.score, Job.url, MatchScore.detail)
        .join(MatchScore, MatchScore.job_id == Job.id)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id)
        .where(MatchScore.scored_at >= since)
        .order_by(MatchScore.score.desc())
    )
    return [MatchOut.model_validate(r, from_attributes=True) for r in (await s.execute(stmt)).all()]


async def send_weekly(s: AsyncSession, sender, now: datetime, top_n: int = 20) -> int:
    since = now - timedelta(days=7)
    user_ids = (await s.execute(select(Resume.user_id).distinct())).scalars().all()

    sent = 0
    for user_id in user_ids:
        matches = await matches_for(s, user_id, since)
        if not matches:
            continue
        await sender.send(user_id, render(matches, top_n))
        sent += 1
    return sent
