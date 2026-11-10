import pytest

pytestmark = pytest.mark.asyncio


async def test_places_are_public_and_carry_their_aliases(client):
    r = await client.get("/places")
    assert r.status_code == 200
    by_name = {p["name"]: p["aliases"] for p in r.json()}
    assert "plano" in by_name["Dallas-Fort Worth"]
    assert "usa" in by_name["United States"]
