import pytest
from sqlalchemy import select

from app.api import deps_api, limits_api
from app.db.models_db import User
from tests.conftest import signup


@pytest.fixture
def outbox(client):
    from app.main import app

    sent = []

    async def capture(msg):
        sent.append(msg)

    app.dependency_overrides[deps_api.get_mailer] = lambda: capture
    yield sent
    app.dependency_overrides.pop(deps_api.get_mailer, None)


def link_token(msg) -> str:
    import re

    return re.search(r"/verify#(\S+)", msg.get_content()).group(1)


async def test_register_then_log_in_gives_a_token_that_works(client):
    token = await signup(client, "a@x.com")
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@x.com"


async def test_register_starts_no_session(client):
    r = await client.post(
        "/auth/register", json={"email": "nosession@x.com", "password": "correct-horse-battery"}
    )
    assert r.status_code == 202 and "set-cookie" not in r.headers and "access_token" not in r.json()


async def test_register_answers_the_same_for_a_taken_email(client, outbox):
    body = {"email": "dup@x.com", "password": "correct-horse-battery"}
    first = await client.post("/auth/register", json=body)
    await client.post("/auth/verify", json={"token": link_token(outbox[-1])})
    client.cookies.clear()
    again = await client.post("/auth/register", json={"email": "DUP@x.com", "password": "another-password"})
    assert (
        (first.status_code, first.json())
        == (again.status_code, again.json())
        == (202, {"detail": "Check your email to finish signing up."})
    )
    assert "already have" in outbox[-1]["Subject"] and outbox[-1]["To"] == "dup@x.com"
    login = await client.post("/auth/login", json={"email": "dup@x.com", "password": "another-password"})
    assert login.status_code == 401
    client.cookies.clear()


async def test_signing_up_again_before_confirming_resends_the_link(client, outbox):
    body = {"email": "lost@x.com", "password": "correct-horse-battery"}
    await client.post("/auth/register", json=body)
    await client.post("/auth/register", json=body)
    assert [m["Subject"] for m in outbox] == ["Confirm your email for SkillFit"] * 2


async def test_already_registered_mails_are_capped_per_address(client, outbox):
    await signup(client, "cap@x.com")
    client.cookies.clear()

    limits_api.REGISTER_IP.reset()
    for _ in range(5):
        assert (
            await client.post(
                "/auth/register", json={"email": "cap@x.com", "password": "correct-horse-battery"}
            )
        ).status_code == 202
    assert len(outbox) == 1 + 3


async def test_login_with_right_password_returns_working_token(client):
    await signup(client, "b@x.com", "correct-horse-battery")

    r = await client.post(
        "/auth/login?token=1", json={"email": "b@x.com", "password": "correct-horse-battery"}
    )

    assert r.status_code == 200
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "b@x.com"


async def test_login_failures_are_indistinguishable(client):
    await signup(client, "c@x.com", "correct-horse-battery")

    wrong_pw = await client.post(
        "/auth/login?token=1", json={"email": "c@x.com", "password": "nope-nope-nope"}
    )
    no_user = await client.post(
        "/auth/login?token=1", json={"email": "ghost@x.com", "password": "nope-nope-nope"}
    )

    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


async def test_password_is_never_stored_in_plain_text(client, session):
    await signup(client, "d@x.com", "correct-horse-battery")

    user = (await session.execute(select(User).where(User.email == "d@x.com"))).scalar_one()

    assert user.hashed_password != "correct-horse-battery"
    assert user.hashed_password.startswith("$2")


async def test_long_multibyte_passwords_are_rejected_cleanly_not_500(client):
    r = await client.post("/auth/register", json={"email": "utf@auth.com", "password": "é" * 40})
    assert r.status_code == 422
    assert "72 bytes" in r.text


async def test_login_with_oversized_password_is_401_not_500(client):
    await signup(client, "big@auth.com", "correct-horse")
    r = await client.post("/auth/login?token=1", json={"email": "big@auth.com", "password": "😀" * 36})
    assert r.status_code == 401


async def test_validation_errors_never_echo_what_was_sent(client):
    r = await client.post("/auth/register", json={"email": "echo@auth.com", "password": "s3cr"})
    assert r.status_code == 422
    assert "s3cr" not in r.text
    assert all("input" not in e for e in r.json()["detail"])


async def test_login_sets_an_httponly_lax_session_cookie_that_authenticates(client):
    try:
        await signup(client, "cookie@auth.com", "correct-horse")
        client.cookies.clear()
        r = await client.post(
            "/auth/login?token=1", json={"email": "cookie@auth.com", "password": "correct-horse"}
        )
        cookie = r.headers["set-cookie"].lower()
        assert "jobbot_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        assert (await client.get("/auth/me")).status_code == 200
    finally:
        client.cookies.clear()


async def test_logout_clears_the_session_cookie(client):
    try:
        await signup(client, "bye@auth.com", "correct-horse")
        assert (await client.get("/auth/me")).status_code == 200
        assert (await client.post("/auth/logout")).status_code == 204
        assert (await client.get("/auth/me")).status_code == 401
    finally:
        client.cookies.clear()


async def test_browser_login_gets_only_the_cookie_no_token_in_body(client):
    try:
        await signup(client, "nobody-reads@auth.com", "correct-horse")
        r = await client.post(
            "/auth/login", json={"email": "nobody-reads@auth.com", "password": "correct-horse"}
        )
        assert r.json().get("access_token") is None
        assert "jobbot_session=" in r.headers["set-cookie"]
    finally:
        client.cookies.clear()


async def test_logout_revokes_tokens_but_a_fresh_login_works(client):
    try:
        tok = await signup(client, "revoke@auth.com", "correct-horse")
        h = {"Authorization": f"Bearer {tok}"}
        assert (await client.get("/auth/me", headers=h)).status_code == 200
        assert (await client.post("/auth/logout", headers=h)).status_code == 204
        assert (await client.get("/auth/me", headers=h)).status_code == 401
        new = (
            await client.post(
                "/auth/login?token=1", json={"email": "revoke@auth.com", "password": "correct-horse"}
            )
        ).json()["access_token"]
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {new}"})).status_code == 200
    finally:
        client.cookies.clear()


async def test_noisy_ip_is_slowed_not_locked_out(client, monkeypatch):

    monkeypatch.setattr(limits_api, "TARPIT_S", 0)
    await signup(client, "nat@auth.com", "correct-horse")
    for _ in range(30):
        limits_api.LOGIN_IP.hit("127.0.0.1")
    r = await client.post("/auth/login?token=1", json={"email": "nat@auth.com", "password": "correct-horse"})
    assert r.status_code == 200
    client.cookies.clear()


async def test_registration_is_rate_limited_per_ip(client):
    for i in range(5):
        assert (
            await client.post(
                "/auth/register", json={"email": f"spam{i}@auth.com", "password": "correct-horse"}
            )
        ).status_code == 202
    r = await client.post("/auth/register", json={"email": "spam5@auth.com", "password": "correct-horse"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    client.cookies.clear()


async def test_api_responses_carry_security_headers(client):
    r = await client.get("/auth/me")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_docs_can_be_switched_off():
    from app.main import docs_kwargs

    assert docs_kwargs(True) == {}
    assert docs_kwargs(False) == {"docs_url": None, "redoc_url": None, "openapi_url": None}


async def test_delete_me_removes_account_resume_and_matches(client, session):
    from sqlalchemy import select

    from app.db.models_db import Job, Resume

    session.add(Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    tok = await signup(client, "gone@auth.com", "correct-horse")
    h = {"Authorization": f"Bearer {tok}"}
    await client.post("/resumes", headers=h, files={"file": ("cv.txt", b"Python developer", "text/plain")})
    me = (await client.get("/auth/me", headers=h)).json()["id"]
    assert (await client.delete("/me", headers=h)).status_code == 204
    assert (await client.get("/auth/me", headers=h)).status_code == 401
    assert (await session.scalars(select(Resume).where(Resume.user_id == me))).all() == []
    client.cookies.clear()


async def test_health_needs_no_login(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


async def test_ready_checks_the_database(client):
    r = await client.get("/ready")
    assert r.status_code == 200 and r.json() == {"ok": True, "db": True}


async def test_ready_says_503_when_the_database_is_down(client):
    from app.core.db_core import get_session
    from app.main import app

    class Down:
        async def execute(self, *a, **k):
            raise OSError("connection refused")

    before = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = lambda: Down()
    try:
        r = await client.get("/ready")
    finally:
        app.dependency_overrides[get_session] = before
    assert r.status_code == 503 and r.json() == {"ok": False, "db": False}


async def test_behind_cloudflare_the_limit_is_per_real_visitor(client, monkeypatch):
    from app.core.config_core import get_settings

    monkeypatch.setattr(get_settings(), "TRUST_CF_CONNECTING_IP", True)
    for i in range(5):
        await client.post(
            "/auth/register",
            headers={"CF-Connecting-IP": "203.0.113.1"},
            json={"email": f"cfa{i}@auth.com", "password": "correct-horse"},
        )
    blocked = await client.post(
        "/auth/register",
        headers={"CF-Connecting-IP": "203.0.113.1"},
        json={"email": "cfa5@auth.com", "password": "correct-horse"},
    )
    other = await client.post(
        "/auth/register",
        headers={"CF-Connecting-IP": "203.0.113.2"},
        json={"email": "cfb@auth.com", "password": "correct-horse"},
    )
    assert (blocked.status_code, other.status_code) == (429, 202)
    client.cookies.clear()


async def test_without_cloudflare_the_header_is_ignored(client):
    for i in range(5):
        await client.post(
            "/auth/register",
            headers={"CF-Connecting-IP": f"198.51.100.{i}"},
            json={"email": f"spoof{i}@auth.com", "password": "correct-horse"},
        )
    r = await client.post(
        "/auth/register",
        headers={"CF-Connecting-IP": "198.51.100.99"},
        json={"email": "spoof9@auth.com", "password": "correct-horse"},
    )
    assert r.status_code == 429
    client.cookies.clear()
