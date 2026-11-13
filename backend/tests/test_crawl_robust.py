import httpx
import pytest
from sqlalchemy import select

from app.db.models_db import Board, Job
from app.ingest import greenhouse_ingest as gh

pytestmark = pytest.mark.asyncio
OK_JOB = {"id": 1, "title": "Backend Engineer", "absolute_url": "https://x/1"}


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def open_jobs(session, board):
    return (
        await session.scalars(
            select(Job)
            .where(Job.board == board, Job.closed_at.is_(None))
            .execution_options(populate_existing=True)
        )
    ).all()


async def test_a_malformed_board_fails_alone(session):
    def handler(req):
        if req.url.path == "/v1/boards/garbage/jobs":
            return httpx.Response(200, text="<html>maintenance</html>")
        if req.url.path == "/v1/boards/nokey/jobs":
            return httpx.Response(200, json={"oops": []})
        if req.url.path == "/v1/boards/good/jobs":
            return httpx.Response(200, json={"jobs": [OK_JOB]})
        return httpx.Response(404)

    async with client(handler) as c:
        summary = await gh.crawl(c, session, ["garbage", "nokey", "good"])
    assert (summary.failed, summary.found, summary.new_jobs) == (2, 1, 1)


async def test_one_malformed_job_is_skipped_but_not_closed(session):
    session.add(Job(board="mixed", external_id="2", title="Old Title"))
    await session.flush()
    bad = {"id": 2, "title": None, "absolute_url": "https://x/2"}
    async with client(lambda req: httpx.Response(200, json={"jobs": [OK_JOB, bad]})) as c:
        summary = await gh.crawl(c, session, ["mixed"])
    assert summary.found == 1 and summary.closed == 0
    assert {j.external_id for j in await open_jobs(session, "mixed")} == {"1", "2"}


async def test_rate_limits_and_server_errors_are_retried(session):
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        if len(calls) == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"jobs": [OK_JOB]})

    async with client(handler) as c:
        summary = await gh.crawl(c, session, ["busy"])
    assert summary.found == 1 and len([1 for _ in calls]) >= 3


async def test_a_board_that_404s_three_crawls_in_a_row_gets_closed(session):
    session.add(Job(board="gone", external_id="1", title="Engineer"))
    await session.flush()
    async with client(lambda req: httpx.Response(404)) as c:
        for crawl_no in (1, 2):
            await gh.crawl(c, session, ["gone"])
            assert len(await open_jobs(session, "gone")) == 1, crawl_no
        summary = await gh.crawl(c, session, ["gone"])
    assert summary.closed == 1 and await open_jobs(session, "gone") == []


async def test_a_good_crawl_resets_the_404_count(session):
    async with client(lambda req: httpx.Response(404)) as c:
        await gh.crawl(c, session, ["blinky"])
        await gh.crawl(c, session, ["blinky"])
    async with client(lambda req: httpx.Response(200, json={"jobs": [OK_JOB]})) as c:
        await gh.crawl(c, session, ["blinky"])
    board = (
        await session.scalars(
            select(Board).where(Board.slug == "blinky").execution_options(populate_existing=True)
        )
    ).one()
    assert board.misses == 0


async def test_boards_dropped_from_the_list_are_retired(session):
    session.add_all(
        [Job(board="kept", external_id="1", title="A"), Job(board="dropped", external_id="1", title="B")]
    )
    await session.flush()
    assert await gh.retire_dropped(session, ["kept"]) == 1
    assert len(await open_jobs(session, "kept")) == 1 and await open_jobs(session, "dropped") == []


async def test_one_bad_posting_never_stops_the_details_run(session):
    session.add_all(
        [Job(board="dd", external_id="1", title="A"), Job(board="dd", external_id="2", title="B")]
    )
    await session.flush()

    def handler(req):
        if req.url.path.endswith("/1"):
            return httpx.Response(200, text="not json")
        return httpx.Response(200, json={"id": 2, "content": "<p>Build things.</p>"})

    async with client(handler) as c:
        assert await gh.fill_descriptions(c, session) == 1
