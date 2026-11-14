import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api import deps_api, limits_api
from app.core.security_core import create_access_token
from app.db.models_db import Feedback, User
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fresh_limits():
    limits_api.FEEDBACK_USER.reset()
    limits_api.FEEDBACK_IP.reset()
    yield


def use_mailer(send):
    app.dependency_overrides[deps_api.get_mailer] = lambda: send


@pytest.fixture
def outbox():
    sent = []

    async def capture(msg):
        sent.append(msg)

    use_mailer(capture)
    yield sent
    app.dependency_overrides.pop(deps_api.get_mailer, None)


async def account(session, verified=True):
    user = User(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@feedback.test",
        hashed_password="x",
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    session.add(user)
    await session.flush()
    return user, {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


BUG = {"kind": "bug", "message": "The Apply button does nothing", "page": "/matches"}


async def cron(session):
    from app.services.feedback_services import drain

    await drain(session, app.dependency_overrides[deps_api.get_mailer]())


async def rows(session, user):
    return (
        (
            await session.execute(
                select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.created_at)
            )
        )
        .scalars()
        .all()
    )


async def test_a_report_is_acknowledged_by_email_right_away(client, session, outbox):
    user, h = await account(session)
    r = await client.post("/feedback", json=BUG, headers=h)
    assert r.status_code == 202
    ref = r.json()["ref"]
    assert len(outbox) == 1, "sent just after the response, no cron wait"
    assert outbox[0]["To"] == user.email and ref in outbox[0]["Subject"]
    assert "Apply button" not in outbox[0].get_content()
    [fb] = await rows(session, user)
    assert (fb.kind, fb.page, fb.ack_status, fb.attempts) == ("bug", "/matches", "sent", 1)


async def test_a_failed_email_stays_queued_and_goes_out_on_the_next_drain(client, session, outbox):
    user, h = await account(session)

    async def down(msg):
        raise OSError("smtp down")

    use_mailer(down)
    assert (await client.post("/feedback", json=BUG, headers=h)).status_code == 202
    [fb] = await rows(session, user)
    assert (fb.ack_status, fb.attempts) == ("queued", 1)

    async def capture(msg):
        outbox.append(msg)

    use_mailer(capture)
    await client.post("/feedback", json={**BUG, "kind": "idea"}, headers=h)
    assert len(outbox) == 1
    await cron(session)
    assert len(outbox) == 2
    assert [f.ack_status for f in await rows(session, user)] == ["sent", "sent"]


async def test_reports_are_rate_limited_per_account(client, session, outbox):
    _, h = await account(session)
    for _ in range(5):
        assert (await client.post("/feedback", json=BUG, headers=h)).status_code == 202
    r = await client.post("/feedback", json=BUG, headers=h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    _, other = await account(session)
    assert (await client.post("/feedback", json=BUG, headers=other)).status_code == 202


async def test_only_confirmed_accounts_and_sane_input(client, session, outbox):
    _, unconfirmed = await account(session, verified=False)
    assert (await client.post("/feedback", json=BUG, headers=unconfirmed)).status_code == 403
    _, h = await account(session)
    for bad in ({**BUG, "kind": "spam"}, {**BUG, "message": "   "}, {**BUG, "message": "x" * 5001}):
        assert (await client.post("/feedback", json=bad, headers=h)).status_code == 422
    assert outbox == []


async def test_the_page_gets_its_answer_before_any_email_is_sent(session):
    from httpx import ASGITransport, AsyncClient

    _, h = await account(session)
    events = []

    async def slow(msg):
        events.append("mail start")
        await asyncio.sleep(0.2)
        events.append("mail done")

    async def recording(scope, receive, send):
        async def send2(message):
            if message["type"] == "http.response.body" and not message.get("more_body"):
                events.append("response sent")
            await send(message)

        await app(scope, receive, send2)

    use_mailer(slow)
    async with AsyncClient(transport=ASGITransport(app=recording), base_url="http://test") as c:
        assert (await c.post("/feedback", json=BUG, headers=h)).status_code == 202
    assert events == ["response sent", "mail start", "mail done"]


async def test_a_hanging_smtp_server_times_out_and_leaves_it_for_the_cron(client, session, monkeypatch):
    from app.services import feedback_services

    monkeypatch.setattr(feedback_services, "SEND_TIMEOUT_S", 0.1)
    user, h = await account(session)

    async def hangs(msg):
        await asyncio.sleep(60)

    use_mailer(hangs)
    assert (
        await asyncio.wait_for(client.post("/feedback", json=BUG, headers=h), timeout=2)
    ).status_code == 202
    [fb] = await rows(session, user)
    assert (fb.ack_status, fb.attempts) == ("queued", 1)


async def test_a_report_pings_the_owner_without_the_message(client, session, outbox, monkeypatch):
    sent = []

    async def capture(message, transport=None):
        sent.append(message)

    monkeypatch.setattr("app.api.routes.feedback_routes.notify", capture)
    _, h = await account(session)
    ref = (await client.post("/feedback", json=BUG, headers=h)).json()["ref"]
    assert sent == [f"New bug report #{ref}."]
