import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.routes import auth_routes, feedback_routes
from app.core.security_core import create_access_token
from app.db.models_db import Feedback, User
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fresh_limits():
    feedback_routes.FEEDBACK_USER.reset()
    feedback_routes.FEEDBACK_IP.reset()
    yield


def use_mailer(send):
    app.dependency_overrides[auth_routes.get_mailer] = lambda: send


@pytest.fixture
def outbox():
    sent = []

    async def capture(msg):
        sent.append(msg)

    use_mailer(capture)
    yield sent
    app.dependency_overrides.pop(auth_routes.get_mailer, None)


async def account(session, verified=True):
    user = User(id=uuid4(), email=f"{uuid4().hex[:8]}@feedback.test", hashed_password="x",
                email_verified_at=datetime.now(timezone.utc) if verified else None)
    session.add(user)
    await session.flush()
    return user, {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


BUG = {"kind": "bug", "message": "The Apply button does nothing", "page": "/matches"}


async def cron(session):
    """What the feedback CronJob does: drain the queue with the current mailer."""
    from app.services.feedback_services import drain
    await drain(session, app.dependency_overrides[auth_routes.get_mailer]())


async def rows(session, user):
    return (await session.execute(select(Feedback).where(Feedback.user_id == user.id)
                                  .order_by(Feedback.created_at))).scalars().all()


async def test_a_report_is_queued_then_acknowledged_by_email(client, session, outbox):
    user, h = await account(session)
    r = await client.post("/feedback", json=BUG, headers=h)
    assert r.status_code == 202
    ref = r.json()["ref"]
    assert outbox == []                                            # the request only queues it
    await cron(session)
    assert len(outbox) == 1 and outbox[0]["To"] == user.email and ref in outbox[0]["Subject"]
    assert "Apply button" not in outbox[0].get_content()          # the report isn't echoed back
    [fb] = await rows(session, user)
    assert (fb.kind, fb.page, fb.ack_status, fb.attempts) == ("bug", "/matches", "sent", 1)


async def test_a_failed_email_stays_queued_and_goes_out_on_the_next_drain(client, session, outbox):
    user, h = await account(session)

    async def down(msg):
        raise OSError("smtp down")

    use_mailer(down)
    assert (await client.post("/feedback", json=BUG, headers=h)).status_code == 202   # the report is still saved
    await cron(session)
    [fb] = await rows(session, user)
    assert (fb.ack_status, fb.attempts) == ("queued", 1)
    async def capture(msg):
        outbox.append(msg)
    use_mailer(capture)
    await client.post("/feedback", json={**BUG, "kind": "idea"}, headers=h)
    await cron(session)
    assert len(outbox) == 2                                        # the straggler went out too
    assert [f.ack_status for f in await rows(session, user)] == ["sent", "sent"]


async def test_reports_are_rate_limited_per_account(client, session, outbox):
    _, h = await account(session)
    for _ in range(5):
        assert (await client.post("/feedback", json=BUG, headers=h)).status_code == 202
    r = await client.post("/feedback", json=BUG, headers=h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    _, other = await account(session)
    assert (await client.post("/feedback", json=BUG, headers=other)).status_code == 202   # per account


async def test_only_confirmed_accounts_and_sane_input(client, session, outbox):
    _, unconfirmed = await account(session, verified=False)
    assert (await client.post("/feedback", json=BUG, headers=unconfirmed)).status_code == 403
    _, h = await account(session)
    for bad in ({**BUG, "kind": "spam"}, {**BUG, "message": "   "}, {**BUG, "message": "x" * 5001}):
        assert (await client.post("/feedback", json=bad, headers=h)).status_code == 422
    assert outbox == []


async def test_the_request_never_touches_smtp(client, session):
    """Even with SMTP hanging, sending feedback answers right away: the cron does the sending."""
    _, h = await account(session)

    async def hangs(msg):
        await asyncio.sleep(60)

    use_mailer(hangs)
    r = await asyncio.wait_for(client.post("/feedback", json=BUG, headers=h), timeout=2)
    assert r.status_code == 202
