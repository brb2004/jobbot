import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db.models_db import Job, MatchScore, Resume
from app.ingest.greenhouse_ingest import BoardJob, close_missing, crawl, save_board
from app.services.matching_services import match_all


def bj(i):
    return BoardJob(id=i, title=f"Job {i}", absolute_url=f"https://x/{i}")


async def jobs_of(session, board):
    return {j.external_id: j for j in (await session.scalars(select(Job).where(Job.board == board).execution_options(populate_existing=True))).all()}


async def test_missing_jobs_close_and_reopen_when_they_come_back(session):
    await save_board(session, "acme", [bj(1), bj(2)])
    await save_board(session, "other", [bj(2)])                  # same id, different board
    assert await close_missing(session, "acme", [1]) == 1

    acme, other = await jobs_of(session, "acme"), await jobs_of(session, "other")
    assert acme[1].closed_at is None
    assert acme[2].closed_at is not None
    assert other[2].closed_at is None                            # other boards untouched

    await save_board(session, "acme", [bj(1), bj(2)])            # it's back
    assert (await jobs_of(session, "acme"))[2].closed_at is None


async def test_failed_board_fetch_closes_nothing(session):
    await save_board(session, "flaky", [bj(1)])
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as client:
        summary = await crawl(client, session, ["flaky"])
    assert summary.failed == 1
    assert (await jobs_of(session, "flaky"))[1].closed_at is None


async def test_match_all_skips_closed_jobs(session):
    open_job = Job(title="Open", skills=["Python"])
    gone = Job(title="Gone", skills=["Python"], closed_at=datetime.now(timezone.utc))
    resume = Resume(user_id=uuid.uuid4(), skills=["Python"])
    session.add_all([open_job, gone, resume])
    await session.flush()
    await match_all(session)
    rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).all()
    assert [r.job_id for r in rows] == [open_job.id]


async def test_titles_are_stripped_on_ingest(session):
    await save_board(session, "trim", [BoardJob(id=1, title="  Security Analyst \n", absolute_url="https://x/1")])
    assert (await jobs_of(session, "trim"))[1].title == "Security Analyst"
