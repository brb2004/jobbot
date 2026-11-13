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


async def test_places_say_what_kind_they_are(client):
    kind = {p["name"]: p["kind"] for p in (await client.get("/places")).json()}
    assert (kind["Dallas-Fort Worth"], kind["Canada"], kind["Europe"]) == ("metro", "country", "region")
    assert "Tel Aviv" not in kind


async def test_places_carry_city_state_labels(client):
    label = {p["name"]: p["label"] for p in (await client.get("/places")).json()}
    assert (label["Vancouver"], label["Vancouver WA"], label["London"]) == (
        "Vancouver, BC",
        "Vancouver, WA",
        "London, United Kingdom",
    )
    assert label["Canada"] == "Canada"
