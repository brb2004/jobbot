import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.api.routes import auth_routes
from app.core.security_core import make_reset_token
from app.db.models_db import Job, MatchScore, Resume, User
from app.main import app
from app.services.digest_services import send_weekly

pytestmark = pytest.mark.asyncio


@pytest.fixture
def outbox(client):
    sent = []

    async def capture(msg):
        sent.append(msg)

    app.dependency_overrides[auth_routes.get_mailer] = lambda: capture
    yield sent
    app.dependency_overrides.pop(auth_routes.get_mailer, None)


def link_token(msg) -> str:
    return re.search(r"/verify#(\S+)", msg.get_content()).group(1)


async def register(client, email="verify@example.com"):
    r = await client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 201
    return email


async def test_signup_emails_a_link_that_confirms_the_address(client, outbox):
    email = await register(client)
    assert len(outbox) == 1 and outbox[0]["To"] == email
    assert (await client.get("/auth/me")).json()["email_verified_at"] is None
    assert (await client.post("/auth/verify", json={"token": link_token(outbox[0])})).status_code == 204
    assert (await client.get("/auth/me")).json()["email_verified_at"] is not None
    again = await client.post("/auth/verify", json={"token": link_token(outbox[0])})
    assert again.status_code == 204                      # clicking twice is harmless


async def test_a_reset_token_cannot_confirm_an_email(client, session):
    email = await register(client)
    user = (await session.execute(select(User).where(User.email == email))).scalar_one()
    reset = make_reset_token(str(user.id), user.hashed_password)
    for token in (reset, "garbage", "not-a-uuid.123.abc", ""):
        assert (await client.post("/auth/verify", json={"token": token})).status_code == 400, token


async def test_resend_is_limited_and_stops_once_confirmed(client, outbox):
    await register(client)                               # 1 email at sign-up
    for _ in range(4):
        assert (await client.post("/auth/verify/resend")).status_code == 202
    assert len(outbox) == 1 + 3
    await client.post("/auth/verify", json={"token": link_token(outbox[0])})
    from app.api.routes.auth_routes import VERIFY_RESEND
    VERIFY_RESEND.reset()
    await client.post("/auth/verify/resend")
    assert len(outbox) == 4                              # confirmed: nothing more to send


async def test_digest_skips_unconfirmed_addresses(session):
    now = datetime.now(timezone.utc)
    job = Job(title="Backend Engineer", board="acme", external_id=1, url="https://example.com/1")
    session.add(job)
    await session.flush()
    ids = {}
    for name, confirmed in (("yes", now), ("no", None)):
        user = User(email=f"{name}@example.com", hashed_password="x", email_verified_at=confirmed)
        session.add(user)
        await session.flush()
        resume = Resume(user_id=user.id, filename="cv.txt")
        session.add(resume)
        await session.flush()
        session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.8, detail={}))
        ids[name] = user.id
    await session.flush()

    sent = []

    class Sender:
        async def send(self, user_id, body):
            sent.append(user_id)

    assert await send_weekly(session, Sender(), now) == 1
    assert sent == [ids["yes"]]
