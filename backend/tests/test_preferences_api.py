async def register(client, email):
    r = await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_put_then_get_returns_what_was_saved(client):
    h = await register(client, "put@prefs.com")
    body = {"include_titles": ["engineer"], "exclude_titles": ["senior"], "locations": ["remote"], "remote_regions": ["us"]}

    assert (await client.put("/me/preferences", json=body, headers=h)).status_code == 200
    assert (await client.get("/me/preferences", headers=h)).json() == body


async def test_new_users_have_empty_preferences(client):
    h = await register(client, "new@prefs.com")
    assert (await client.get("/me/preferences", headers=h)).json() == {"include_titles": [], "exclude_titles": [], "locations": [], "remote_regions": []}


async def test_users_only_see_their_own_preferences(client):
    alice = await register(client, "alice@prefs.com")
    bob = await register(client, "bob@prefs.com")

    await client.put("/me/preferences", json={"exclude_titles": ["senior"]}, headers=alice)

    assert (await client.get("/me/preferences", headers=bob)).json() == {"include_titles": [], "exclude_titles": [], "locations": [], "remote_regions": []}


async def test_wrong_shape_is_rejected(client):
    h = await register(client, "shape@prefs.com")
    r = await client.put("/me/preferences", json={"include_titles": "engineer"}, headers=h)   # string, not list
    assert r.status_code == 422


async def test_unknown_fields_are_rejected(client):
    h = await register(client, "extra@prefs.com")
    r = await client.put("/me/preferences", json={"is_admin": True}, headers=h)
    assert r.status_code == 422


async def test_requires_a_token(client):
    assert (await client.get("/me/preferences")).status_code == 401
