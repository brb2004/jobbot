async def test_register_returns_a_token_that_works(client):
    r = await client.post("/auth/register",
                          json={"email": "a@x.com", "password": "correct-horse-battery"})
    assert r.status_code == 201

    token = r.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "a@x.com"