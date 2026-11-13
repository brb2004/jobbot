import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import DigestSent, Job, MatchScore, Resume, User
from app.schemas.matches_schemas import MatchOut
from app.services.matches_services import marked
from app.services.requirements_services import years_note
from app.services.scoring_services import TIERS, tier  # noqa: F401  (re-exported)

SHOW = 3  # requirements shown per list
log = logging.getLogger(__name__)
WIDTH = 80  # characters per requirement before trimming


def _short(items: list[str]) -> str:
    trimmed = [i if len(i) <= WIDTH else i[: WIDTH - 1].rstrip() + "…" for i in items[:SHOW]]
    more = f" (+{len(items) - SHOW} more)" if len(items) > SHOW else ""
    return "; ".join(trimmed) + more


def _blocks(best: list[MatchOut]) -> list[str]:
    blocks = []
    for i, m in enumerate(best, 1):
        d = m.detail or {}
        head = f"{i}. {m.title} — {tier(m.score)}"
        if d.get("over_years") and (note := years_note(d)):
            head += f" · {note}"  # email: only flag when it's over your level
        if d.get("clearance"):
            head += " · may require clearance or U.S. citizenship"
        total = len(d.get("met") or []) + len(d.get("partial") or []) + len(d.get("missing") or [])
        if total:
            head += f" · {len(d.get('met') or [])} of {total} skills"
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
    return blocks


def render(matches: list[MatchOut], top_n: int) -> str:
    if not matches:
        return "No new matches this week."
    best: dict = {}
    for m in matches:
        if m.job_id not in best or m.score > best[m.job_id].score:
            best[m.job_id] = m
    ranked = sorted(best.values(), key=lambda m: m.score, reverse=True)
    names = list(dict.fromkeys(m.resume for m in ranked))
    if len(names) < 2:
        return "Your top matches this week:\n\n" + "\n\n".join(_blocks(ranked[:top_n]))
    per = max(1, top_n // len(names))
    sections = [
        f"== {name or 'Resume'} ==\n\n" + "\n\n".join(_blocks([m for m in ranked if m.resume == name][:per]))
        for name in names
    ]
    return "Your top matches this week:\n\n" + "\n\n".join(sections)


async def matches_for(s: AsyncSession, user_id: UUID, since: datetime):
    stmt = (
        select(
            Job.id.label("job_id"),
            Job.title,
            MatchScore.score,
            Job.url,
            MatchScore.detail,
            Resume.name.label("resume"),
        )
        .join(MatchScore, MatchScore.job_id == Job.id)
        .join(Resume, Resume.id == MatchScore.resume_id)
        .where(Resume.user_id == user_id)
        .where(MatchScore.scored_at >= since)
        .where(Job.closed_at.is_(None))  # never email a dead link
        .where(Job.id.not_in(marked(user_id)))  # nor a job they already applied to or dismissed
        .order_by(MatchScore.score.desc())
    )
    return [MatchOut.model_validate(r, from_attributes=True) for r in (await s.execute(stmt)).all()]


async def send_weekly(s: AsyncSession, sender, now: datetime, top_n: int = 20) -> int:
    since = now - timedelta(days=7)
    unconfirmed = exists().where(
        User.id == Resume.user_id, User.email_verified_at.is_(None) | User.digest_opt_out_at.is_not(None)
    )
    user_ids = (await s.execute(select(Resume.user_id).distinct().where(~unconfirmed))).scalars().all()

    year, wk, _ = now.isocalendar()
    week = f"{year}-W{wk:02d}"
    done = set((await s.scalars(select(DigestSent.user_id).where(DigestSent.week == week))).all())
    sent = 0
    for user_id in user_ids:
        if user_id in done:
            continue  # already sent this week: re-running the job is safe
        matches = await matches_for(s, user_id, since)
        if not matches:
            continue
        s.add(DigestSent(user_id=user_id, week=week))  # claim first: a crash after sending can't resend
        await s.commit()
        try:
            await sender.send(user_id, render(matches, top_n))
        except Exception:  # one bad address or SMTP hiccup: log it, keep going
            log.exception("weekly digest to %s failed", user_id)
            await s.execute(delete(DigestSent).where(DigestSent.user_id == user_id, DigestSent.week == week))
            await s.commit()  # unclaimed: the next run retries this user
            continue
        sent += 1
    return sent
