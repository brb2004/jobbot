import pytest

pytestmark = pytest.mark.asyncio


async def test_places_are_public_and_carry_their_aliases(client):
    r = await client.get("/places")
    assert r.status_code == 200
    by_name = {p["name"]: p["aliases"] for p in r.json()}
    assert "plano" in by_name["Dallas-Fort Worth"]
    assert "usa" in by_name["United States"]


async def test_skills_are_public_and_carry_their_aliases(client):
    r = await client.get("/skills")
    assert r.status_code == 200
    by_name = {s["name"]: s["aliases"] for s in r.json()}
    assert "PostgreSQL" in by_name and "postgres" in by_name["PostgreSQL"]


async def test_asia_pacific_is_spelled_out(client):
    by_name = {p["name"]: p["aliases"] for p in (await client.get("/places")).json()}
    assert "apac" in by_name["Asia-Pacific"]
