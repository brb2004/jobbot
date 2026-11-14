from tests.conftest import signup


async def register(client, email):
    return {"Authorization": f"Bearer {await signup(client, email)}"}


async def test_put_then_get_returns_what_was_saved(client):
    h = await register(client, "put@prefs.com")
    body = {
        "include_titles": ["engineer"],
        "exclude_titles": ["senior"],
        "locations": ["us"],
        "remote": True,
        "onsite": False,
        "years_experience": 2,
        "extra_skills": ["Go"],
        "include_presales": False,
        "education": "associate",
    }

    assert (await client.put("/me/preferences", json=body, headers=h)).status_code == 200
    assert (await client.get("/me/preferences", headers=h)).json() == body


async def test_new_users_have_empty_preferences(client):
    h = await register(client, "new@prefs.com")
    assert (await client.get("/me/preferences", headers=h)).json() == {
        "include_titles": [],
        "exclude_titles": [],
        "locations": [],
        "remote": True,
        "onsite": True,
        "years_experience": None,
        "extra_skills": [],
        "include_presales": False,
        "education": None,
    }


async def test_users_only_see_their_own_preferences(client):
    alice = await register(client, "alice@prefs.com")
    bob = await register(client, "bob@prefs.com")

    await client.put("/me/preferences", json={"exclude_titles": ["senior"]}, headers=alice)

    assert (await client.get("/me/preferences", headers=bob)).json() == {
        "include_titles": [],
        "exclude_titles": [],
        "locations": [],
        "remote": True,
        "onsite": True,
        "years_experience": None,
        "extra_skills": [],
        "include_presales": False,
        "education": None,
    }


async def test_wrong_shape_is_rejected(client):
    h = await register(client, "shape@prefs.com")
    r = await client.put("/me/preferences", json={"include_titles": "engineer"}, headers=h)
    assert r.status_code == 422


async def test_unknown_fields_are_rejected(client):
    h = await register(client, "extra@prefs.com")
    r = await client.put("/me/preferences", json={"is_admin": True}, headers=h)
    assert r.status_code == 422


async def test_requires_a_token(client):
    assert (await client.get("/me/preferences")).status_code == 401


async def test_saving_preferences_rematches_immediately(client, session):
    from app.db.models_db import Job

    h = await register(client, "rematch@prefs.com")
    from sqlalchemy import func, update

    from app.db.models_db import User

    await session.execute(
        update(User).where(User.email == "rematch@prefs.com").values(email_verified_at=func.now())
    )
    session.add_all(
        [Job(title="Senior Engineer", skills=["Python"]), Job(title="Engineer", skills=["Python"])]
    )
    await session.flush()
    await client.post("/resumes", headers=h, files={"file": ("cv.txt", b"Python", "text/plain")})
    assert len((await client.get("/dashboard", headers=h)).json()) == 2

    await client.put("/me/preferences", headers=h, json={"exclude_titles": ["senior"]})
    assert [m["title"] for m in (await client.get("/dashboard", headers=h)).json()] == ["Engineer"]


async def test_validation_messages_are_plain_english(client):
    h = await register(client, "plain@prefs.com")
    r = await client.put(
        "/me/preferences", headers=h, json={"include_titles": ["senior"], "exclude_titles": ["senior"]}
    )
    assert r.status_code == 422
    assert "Value error" not in r.text and "both" in r.text
    r = await client.post("/auth/register", json={"email": "short@prefs.com", "password": "abc"})
    assert r.json()["detail"][0]["msg"] == "must be at least 8 characters"
