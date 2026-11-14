import pytest
from pydantic import ValidationError

from app.services.links_services import Links
from tests.conftest import signup


async def register(client, email):
    return {"Authorization": f"Bearer {await signup(client, email)}"}


async def test_links_are_saved_per_user(client):
    me = await register(client, "links@me.com")
    them = await register(client, "links@them.com")
    body = {"linkedin": "linkedin.com/in/me", "github": "https://github.com/me", "website": None}
    saved = (await client.put("/me/links", json=body, headers=me)).json()
    assert saved["linkedin"] == "https://linkedin.com/in/me"
    assert (await client.get("/me/links", headers=me)).json() == saved
    assert (await client.get("/me/links", headers=them)).json() == {
        "linkedin": None,
        "github": None,
        "website": None,
    }


def test_blank_means_none():
    assert Links(github="   ").github is None


@pytest.mark.parametrize(
    "bad",
    [
        "javascript:alert(1)",
        "ftp://files.me",
        "not a url",
        "localhost",
        "https://x.com/" + "a" * 200,
        'a.com/"x',
    ],
)
def test_only_web_addresses_are_kept(bad):
    with pytest.raises(ValidationError):
        Links(website=bad)


async def test_links_need_a_login(client):
    assert (await client.get("/me/links")).status_code == 401
