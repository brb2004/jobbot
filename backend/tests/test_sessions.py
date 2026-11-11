"""Secure defaults, per-account login slowdown, sliding sessions."""
import time

import jwt
import pytest

from app.api.routes import auth_routes
from app.core.config_core import Settings, get_settings
from tests.conftest import signup



def test_defaults_are_the_production_ones(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("DOCS_ENABLED", raising=False)
    s = Settings(_env_file=None, DATABASE_URL="postgresql+asyncpg://x/y", JWT_SECRET_KEY="k" * 32)
    assert s.COOKIE_SECURE is True and s.DOCS_ENABLED is False


def test_refuses_to_start_with_a_short_jwt_secret():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        Settings(_env_file=None, DATABASE_URL="postgresql+asyncpg://x/y", JWT_SECRET_KEY="changeme")


def test_account_delay_grows_then_caps():
    delays = [auth_routes.account_delay(n) for n in range(12)]
    assert delays[:5] == [0] * 5
    assert delays[5:10] == [1, 2, 4, 8, 16] and max(delays) == 16


async def test_guessing_one_account_from_many_ips_slows_down_but_never_locks_out(client, monkeypatch):
    from app.core.config_core import get_settings
    monkeypatch.setattr(get_settings(), "TRUST_CF_CONNECTING_IP", True)
    slept = []

    async def fake_sleep(s):
        slept.append(s)
    monkeypatch.setattr(auth_routes.asyncio, "sleep", fake_sleep)
    await signup(client, "target@slow.example.com", "correct-horse")
    client.cookies.clear()
    for i in range(8):                                   # 8 ips, one guess each: the per-ip limits never trip
        r = await client.post("/auth/login", headers={"CF-Connecting-IP": f"203.0.113.{i}"},
                              json={"email": "target@slow.example.com", "password": "wrong-guess"})
        assert r.status_code == 401
    assert slept == [1, 2, 4]                            # 6th, 7th, 8th guesses waited
    ok = await client.post("/auth/login", headers={"CF-Connecting-IP": "198.51.100.7"},
                           json={"email": "target@slow.example.com", "password": "correct-horse"})
    assert ok.status_code == 200                         # the owner still gets in (after a wait)
    assert auth_routes.LOGIN_EMAIL.count("target@slow.example.com") == 0    # and the slowdown resets
    client.cookies.clear()


def _cookie_token(user_id: str, age_s: float) -> str:
    s = get_settings()
    now = time.time()
    return jwt.encode({"sub": user_id, "iat": now - age_s, "exp": now - age_s + s.ACCESS_TOKEN_EXPIRE_MINUTES * 60},
                      s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


async def test_an_active_session_slides_forward(client):
    await signup(client, "slide@sess.example.com")
    me = (await client.get("/auth/me")).json()["id"]
    life = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    try:
        client.cookies.set("jobbot_session", _cookie_token(me, age_s=life * 0.2))
        assert "set-cookie" not in (await client.get("/auth/me")).headers      # fresh enough: left alone
        client.cookies.set("jobbot_session", _cookie_token(me, age_s=life * 0.6))
        r = await client.get("/auth/me")
        assert r.status_code == 200 and "jobbot_session=" in r.headers["set-cookie"]
        new = r.cookies["jobbot_session"]
        assert jwt.decode(new, options={"verify_signature": False})["iat"] > time.time() - 5
    finally:
        client.cookies.clear()


async def test_bearer_tokens_never_slide(client):
    tok = await signup(client, "bearer@sess.example.com")
    client.cookies.clear()
    me = (await client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})).json()["id"]
    old = _cookie_token(me, age_s=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60 * 0.9)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 200 and "set-cookie" not in r.headers


async def test_logout_beats_the_slide(client):
    await signup(client, "out@sess.example.com")
    me = (await client.get("/auth/me")).json()["id"]
    try:
        client.cookies.set("jobbot_session", _cookie_token(me, age_s=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 50))
        assert (await client.post("/auth/logout")).status_code == 204
        assert (await client.get("/auth/me")).status_code == 401
    finally:
        client.cookies.clear()
