"""Edited postings are fetched again; old closed postings shrink, then go (unless someone applied)."""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.db.models_db import Application, Job, MatchScore, Resume
from app.ingest import greenhouse_ingest as gh
from app.ingest.greenhouse_ingest import BoardJob, save_board
from app.services.extraction_services import fill_job_requirements
from app.services.matching_services import tag_jobs
from app.services.retention_services import prune
from tests.conftest import user_row

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)


def bj(i, updated):
    return BoardJob(id=i, title=f"Job {i}", absolute_url=f"https://x/{i}", updated_at=updated)


async def job(session, board, ext):
    return (await session.scalars(select(Job).where(Job.board == board, Job.external_id == ext)
                                  .execution_options(populate_existing=True))).one()


async def test_an_edited_posting_is_fetched_again_and_retagged(session):
    await save_board(session, "edits", [bj(1, "2026-11-01T00:00:00-05:00"), bj(2, "2026-11-01T00:00:00-05:00")])
    for ext in (1, 2):
        j = await job(session, "edits", ext)
        j.description, j.content_html = "old", "<h3>Requirements</h3><ul><li>Python</li></ul>"
    await session.commit()
    await fill_job_requirements(session)
    await tag_jobs(session)
    assert (await job(session, "edits", 1)).skills == ["Python"]

    await save_board(session, "edits", [bj(1, "2026-11-09T10:00:00-05:00"), bj(2, "2026-11-01T00:00:00-05:00")])
    edited, same = await job(session, "edits", 1), await job(session, "edits", 2)
    assert edited.description is None and edited.skills == ["Python"]   # refetch queued; still matchable meanwhile
    assert same.description == "old"                                     # unchanged: no refetch

    def handler(req):
        return httpx.Response(200, json={"content": "<h3>Requirements</h3><ul><li>Rust</li></ul>"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        assert await gh.fill_descriptions(c, session) == 1
    await fill_job_requirements(session)
    await tag_jobs(session)
    assert (await job(session, "edits", 1)).skills == ["Rust"]


async def test_rows_from_before_the_column_existed_are_not_all_refetched(session):
    await save_board(session, "legacy", [BoardJob(id=1, title="Job", absolute_url="https://x/1")])  # no updated_at
    j = await job(session, "legacy", 1)
    j.description = "kept"
    await session.commit()
    await save_board(session, "legacy", [bj(1, "2026-11-09T10:00:00-05:00")])
    j = await job(session, "legacy", 1)
    assert j.description == "kept" and j.source_updated_at == "2026-11-09T10:00:00-05:00"


async def test_closed_postings_shrink_after_30_days_and_go_after_90(session):
    def closed(days, title):
        return Job(title=title, description="d", content_html="<p>big</p>", closed_at=NOW - timedelta(days=days))
    open_, recent, month, old, applied = (Job(title="open", description="d", content_html="<p>x</p>"),
                                          closed(10, "recent"), closed(40, "month"), closed(100, "old"),
                                          closed(100, "applied"))
    owner = user_row()
    resume = Resume(user=owner, skills=["Python"])
    session.add_all([open_, recent, month, old, applied, resume])
    await session.flush()
    session.add_all([Application(user_id=owner.id, job_id=applied.id),
                     MatchScore(resume_id=resume.id, job_id=old.id, score=0.5)])
    await session.commit()

    result = await prune(session, now=NOW)

    rows = {j.title: j for j in (await session.scalars(select(Job).execution_options(populate_existing=True))).all()
            if j.title in {"open", "recent", "month", "old", "applied"}}
    assert set(rows) == {"open", "recent", "month", "applied"}            # "old" deleted
    assert rows["open"].content_html and rows["recent"].content_html      # untouched
    assert rows["month"].content_html is None and rows["month"].description is None
    assert rows["applied"].content_html is None                           # kept for the Applied tab, slimmed
    assert (await session.scalars(select(MatchScore).where(MatchScore.job_id == old.id))).all() == []
    assert (result.cleared, result.deleted) == (3, 1)
