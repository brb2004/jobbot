import httpx
from app.ingest import greenhouse_ingest as gh


def fake_greenhouse(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/boards/stripe/jobs":
        return httpx.Response(200, json={"jobs": [
            {"id": 1, "title": "Backend Engineer", "absolute_url": "https://x/1",
             "updated_at": "2026-10-01T00:00:00Z", "location": {"name": "Remote"}},
        ]})
    return httpx.Response(404)


def client():
    return httpx.AsyncClient(transport=httpx.MockTransport(fake_greenhouse))


async def test_fetch_board_returns_jobs():
    async with client() as c:
        jobs = await gh.fetch_board(c, "stripe")

    assert [j.title for j in jobs] == ["Backend Engineer"]
    assert jobs[0].location == "Remote"


async def test_fetch_board_returns_none_when_not_on_greenhouse():
    async with client() as c:
        assert await gh.fetch_board(c, "notacompany") is None