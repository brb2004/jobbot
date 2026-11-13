import re
import time

import pytest
from sqlalchemy import select

from app.api.routes import auth_routes
from app.core.config_core import get_settings
from app.core.security_core import make_reset_token
from app.db.models_db import User
from app.main import app

pytestmark = pytest.mark.asyncio
OLD, NEW = "correct-horse-1", "new-password-22"


@pytest.fixture
def outbox(client):
    sent = []

    async def capture(msg):
        if msg["Subject"].startswith("Reset"):  # sign-up also sends a confirmation email
            sent.append(msg)

    app.dependency_overrides[auth_routes.get_mailer] = lambda: capture
    yield sent
    app.dependency_overrides.pop(auth_routes.get_mailer, None)


def link_token(msg) -> str:
    return re.search(r"/reset#(\S+)", msg.get_content()).group(1)


async def register(client, email="reset@example.com"):
    r = await client.post("/auth/register", json={"email": email, "password": OLD})
    assert r.status_code == 202
    assert (
        await client.post("/auth/login", json={"email": email, "password": OLD})
    ).status_code == 200  # cookie
    return email


async def test_link_resets_the_password_exactly_once(client, outbox):
    email = await register(client)
    assert (await client.post("/auth/forgot", json={"email": email.upper()})).status_code == 202
    assert len(outbox) == 1 and outbox[0]["To"] == email
    token = link_token(outbox[0])
    assert (await client.post("/auth/reset", json={"token": token, "password": NEW})).status_code == 204
    assert (await client.post("/auth/login", json={"email": email, "password": OLD})).status_code == 401
    assert (await client.post("/auth/login", json={"email": email, "password": NEW})).status_code == 200
    again = await client.post("/auth/reset", json={"token": token, "password": "third-password-3"})
    assert again.status_code == 400  # password hash changed, so the link is dead


async def test_unknown_email_gets_the_same_answer_and_no_mail(client, outbox):
    email = await register(client)
    known = await client.post("/auth/forgot", json={"email": email})
    unknown = await client.post("/auth/forgot", json={"email": "nobody@example.com"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert [m["To"] for m in outbox] == [email]


async def test_reset_signs_out_existing_sessions(client, outbox):
    email = await register(client)  # client now holds a session cookie
    assert (await client.get("/auth/me")).status_code == 200
    await client.post("/auth/forgot", json={"email": email})
    await client.post("/auth/reset", json={"token": link_token(outbox[0]), "password": NEW})
    assert (await client.get("/auth/me")).status_code == 401


async def test_expired_tampered_and_garbage_tokens_fail(client, session):
    email = await register(client)
    user = (await session.execute(select(User).where(User.email == email))).scalar_one()
    expired = make_reset_token(str(user.id), user.hashed_password, now=time.time() - 3600)
    good = make_reset_token(str(user.id), user.hashed_password)
    tampered = good[:-1] + ("0" if good[-1] != "0" else "1")
    for token in (expired, tampered, "garbage", "not-a-uuid.123.abc", ""):
        r = await client.post("/auth/reset", json={"token": token, "password": NEW})
        assert r.status_code == 400, token


async def test_link_uses_app_url_not_the_host_header(client, outbox):
    email = await register(client)
    await client.post("/auth/forgot", json={"email": email}, headers={"Host": "evil.example"})
    body = outbox[0].get_content()
    assert f"{get_settings().APP_URL}/reset#" in body and "evil.example" not in body


async def test_one_address_gets_at_most_three_emails_an_hour(client, outbox):
    email = await register(client)
    for _ in range(5):
        assert (await client.post("/auth/forgot", json={"email": email})).status_code == 202
    assert len(outbox) == 3
