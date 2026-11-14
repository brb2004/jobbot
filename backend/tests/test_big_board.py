import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.db.models_db import Job
from app.ingest import crawl_ingest
from app.ingest import greenhouse_ingest as gh
from app.ingest.crawl_ingest import Posting, save_postings


def _postings(n: int, html: str | None = None) -> list[Posting]:
    return [
        Posting(
            external_id=str(i),
            title=f"Engineer {i}",
            url=f"https://x/{i}",
            content_html=html,
            description=html,
        )
        for i in range(n)
    ]


@pytest.mark.parametrize("html", [None, "<p>Python</p>"])
async def test_a_board_past_the_parameter_limit_still_saves(session, html):
    assert await save_postings(session, "ashby:huge", _postings(3500, html)) == 3500
    assert await session.scalar(select(func.count()).select_from(Job)) == 3500


async def test_a_second_crawl_of_a_big_board_adds_nothing(session):
    await save_postings(session, "ashby:huge", _postings(2500))
    assert await save_postings(session, "ashby:huge", _postings(2500)) == 0


async def test_a_board_that_cannot_be_saved_fails_alone(session, monkeypatch):
    real = crawl_ingest.save_postings

    async def flaky(s, key, postings):
        if key.endswith("broken"):
            raise DBAPIError("INSERT", {}, Exception("too many parameters"))
        return await real(s, key, postings)

    monkeypatch.setattr(crawl_ingest, "save_postings", flaky)
    job = {"id": 1, "title": "Backend Engineer", "absolute_url": "https://x/1"}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"jobs": [job]}))
    async with httpx.AsyncClient(transport=transport) as c:
        summary = await gh.crawl(c, session, ["broken", "good"])
    assert (summary.failed, summary.found, summary.new_jobs) == (1, 1, 1)
