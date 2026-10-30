import pytest
from sqlalchemy import select
from app.db.models_db import User

async def test_register_returns_a_token_that_works(client):
    r = await client.post("/auth/register",
                          json={"email": "a@x.com", "password": "correct-horse-battery"})
    assert r.status_code == 201

    token = r.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "a@x.com"
async def test_register_rejects_duplicate_email_case_insensitive(client):
    body = {"email": "dup@x.com", "password": "correct-horse-battery"}
    assert (await client.post("/auth/register", json=body)).status_code == 201

    again = await client.post("/auth/register",
                              json={"email": "DUP@x.com", "password": "another-password"})

    assert again.status_code == 409
async def test_login_with_right_password_returns_working_token(client):
    await client.post("/auth/register", json={"email": "b@x.com", "password": "correct-horse-battery"})

    r = await client.post("/auth/login", json={"email": "b@x.com", "password": "correct-horse-battery"})

    assert r.status_code == 200
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "b@x.com"


async def test_login_failures_are_indistinguishable(client):
    await client.post("/auth/register", json={"email": "c@x.com", "password": "correct-horse-battery"})

    wrong_pw = await client.post("/auth/login", json={"email": "c@x.com", "password": "nope-nope-nope"})
    no_user  = await client.post("/auth/login", json={"email": "ghost@x.com", "password": "nope-nope-nope"})

    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()

async def test_password_is_never_stored_in_plain_text(client, session):
    await client.post("/auth/register", json={"email": "d@x.com", "password": "correct-horse-battery"})

    user = (await session.execute(select(User).where(User.email == "d@x.com"))).scalar_one()

    assert user.hashed_password != "correct-horse-battery"
    assert user.hashed_password.startswith("$2")  