import pytest
from sqlalchemy import select
from app.db.models_db import User

async def test_register_returns_a_token_that_works(client):
    r = await client.post("/auth/register?token=1",
                          json={"email": "a@x.com", "password": "correct-horse-battery"})
    assert r.status_code == 201

    token = r.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "a@x.com"
async def test_register_rejects_duplicate_email_case_insensitive(client):
    body = {"email": "dup@x.com", "password": "correct-horse-battery"}
    assert (await client.post("/auth/register?token=1", json=body)).status_code == 201

    again = await client.post("/auth/register?token=1",
                              json={"email": "DUP@x.com", "password": "another-password"})

    assert again.status_code == 409
async def test_login_with_right_password_returns_working_token(client):
    await client.post("/auth/register?token=1", json={"email": "b@x.com", "password": "correct-horse-battery"})

    r = await client.post("/auth/login?token=1", json={"email": "b@x.com", "password": "correct-horse-battery"})

    assert r.status_code == 200
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "b@x.com"


async def test_login_failures_are_indistinguishable(client):
    await client.post("/auth/register?token=1", json={"email": "c@x.com", "password": "correct-horse-battery"})

    wrong_pw = await client.post("/auth/login?token=1", json={"email": "c@x.com", "password": "nope-nope-nope"})
    no_user  = await client.post("/auth/login?token=1", json={"email": "ghost@x.com", "password": "nope-nope-nope"})

    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()

async def test_password_is_never_stored_in_plain_text(client, session):
    await client.post("/auth/register?token=1", json={"email": "d@x.com", "password": "correct-horse-battery"})

    user = (await session.execute(select(User).where(User.email == "d@x.com"))).scalar_one()

    assert user.hashed_password != "correct-horse-battery"
    assert user.hashed_password.startswith("$2")  

async def test_long_multibyte_passwords_are_rejected_cleanly_not_500(client):
    r = await client.post("/auth/register?token=1", json={"email": "utf@auth.com", "password": "é" * 40})   # 40 chars, 80 bytes
    assert r.status_code == 422
    assert "72 bytes" in r.text


async def test_login_with_oversized_password_is_401_not_500(client):
    await client.post("/auth/register?token=1", json={"email": "big@auth.com", "password": "correct-horse"})
    r = await client.post("/auth/login?token=1", json={"email": "big@auth.com", "password": "😀" * 36})
    assert r.status_code == 401


async def test_validation_errors_never_echo_what_was_sent(client):
    r = await client.post("/auth/register?token=1", json={"email": "echo@auth.com", "password": "s3cr"})
    assert r.status_code == 422
    assert "s3cr" not in r.text
    assert all("input" not in e for e in r.json()["detail"])


async def test_login_sets_an_httponly_lax_session_cookie_that_authenticates(client):
    try:
        await client.post("/auth/register?token=1", json={"email": "cookie@auth.com", "password": "correct-horse"})
        client.cookies.clear()
        r = await client.post("/auth/login?token=1", json={"email": "cookie@auth.com", "password": "correct-horse"})
        cookie = r.headers["set-cookie"].lower()
        assert "jobbot_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        assert (await client.get("/auth/me")).status_code == 200            # cookie alone, no header
    finally:
        client.cookies.clear()


async def test_logout_clears_the_session_cookie(client):
    try:
        await client.post("/auth/register?token=1", json={"email": "bye@auth.com", "password": "correct-horse"})
        assert (await client.get("/auth/me")).status_code == 200
        assert (await client.post("/auth/logout")).status_code == 204
        assert (await client.get("/auth/me")).status_code == 401
    finally:
        client.cookies.clear()


async def test_browser_login_gets_only_the_cookie_no_token_in_body(client):
    try:
        r = await client.post("/auth/register", json={"email": "nobody-reads@auth.com", "password": "correct-horse"})
        assert r.json().get("access_token") is None
        assert "jobbot_session=" in r.headers["set-cookie"]
    finally:
        client.cookies.clear()


async def test_logout_revokes_tokens_but_a_fresh_login_works(client):
    try:
        tok = (await client.post("/auth/register?token=1", json={"email": "revoke@auth.com", "password": "correct-horse"})).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert (await client.get("/auth/me", headers=h)).status_code == 200
        assert (await client.post("/auth/logout", headers=h)).status_code == 204
        assert (await client.get("/auth/me", headers=h)).status_code == 401          # old token is dead
        new = (await client.post("/auth/login?token=1", json={"email": "revoke@auth.com", "password": "correct-horse"})).json()["access_token"]
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {new}"})).status_code == 200
    finally:
        client.cookies.clear()


async def test_noisy_ip_is_slowed_not_locked_out(client, monkeypatch):
    from app.api.routes import auth_routes
    monkeypatch.setattr(auth_routes, "TARPIT_S", 0)
    await client.post("/auth/register?token=1", json={"email": "nat@auth.com", "password": "correct-horse"})
    for _ in range(30):
        auth_routes.LOGIN_IP.hit("127.0.0.1")                                       # someone else on this network
    r = await client.post("/auth/login?token=1", json={"email": "nat@auth.com", "password": "correct-horse"})
    assert r.status_code == 200
    client.cookies.clear()


async def test_registration_is_rate_limited_per_ip(client):
    for i in range(5):
        assert (await client.post("/auth/register?token=1", json={"email": f"spam{i}@auth.com", "password": "correct-horse"})).status_code == 201
    r = await client.post("/auth/register?token=1", json={"email": "spam5@auth.com", "password": "correct-horse"})
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
    tok = (await client.post("/auth/register?token=1", json={"email": "gone@auth.com", "password": "correct-horse"})).json()["access_token"]
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
