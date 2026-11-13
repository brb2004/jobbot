import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_core import get_settings
from app.db.models_db import Feedback, User
from app.services.email_services import feedback_email

MAX_ATTEMPTS = 5
SEND_TIMEOUT_S = 15
log = logging.getLogger(__name__)


def ref_of(feedback_id: UUID) -> str:
    return str(feedback_id)[:8].upper()


async def submit(
    s: AsyncSession, user_id: UUID, kind: str, message: str, page: str | None, user_agent: str | None
) -> UUID:
    fid = uuid4()
    s.add(
        Feedback(
            id=fid,
            user_id=user_id,
            kind=kind,
            message=message,
            page=page,
            user_agent=user_agent,
            status="open",
            ack_status="queued",
            attempts=0,
        )
    )
    await s.commit()
    return fid


async def drain(s: AsyncSession, send, limit: int = 20, only: UUID | None = None) -> int:
    stmt = (
        select(Feedback, User.email)
        .join(User, User.id == Feedback.user_id)
        .where(Feedback.ack_status == "queued", Feedback.attempts < MAX_ATTEMPTS)
        .order_by(Feedback.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True, of=Feedback)
    )
    if only is not None:
        stmt = stmt.where(Feedback.id == only)
    rows = (await s.execute(stmt)).all()
    st = get_settings()
    sent = 0
    for fb, email in rows:
        fb.attempts += 1
        try:
            await asyncio.wait_for(
                send(feedback_email(st.EMAIL_FROM, email, ref_of(fb.id), fb.kind)), timeout=SEND_TIMEOUT_S
            )
        except Exception:
            log.exception("feedback acknowledgement failed (attempt %s) for %s", fb.attempts, fb.id)
            if fb.attempts >= MAX_ATTEMPTS:
                fb.ack_status = "failed"
            continue
        fb.ack_status, fb.acked_at = "sent", datetime.now(UTC)
        sent += 1
    await s.commit()
    return sent


async def acknowledge_now(sessionmaker, send, feedback_id: UUID) -> None:
    try:
        async with sessionmaker() as s:
            await drain(s, send, limit=1, only=feedback_id)
    except Exception:
        log.exception("immediate feedback acknowledgement failed for %s; the CronJob will retry", feedback_id)
