import httpx
from app.ingest import greenhouse_ingest as gh
from app.db.models_db import Job
from sqlalchemy import select


def fake_greenhouse(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/boards/stripe/jobs":
        return httpx.Response(200, json={"jobs": [
            {"id": 1, "title": "Backend Engineer", "absolute_url": "https://x/1",
             "updated_at": "2026-10-01T00:00:00Z", "location": {"name": "Remote"}},
        ]})
    if request.url.path == "/v1/boards/broken/jobs":
        return httpx.Response(500)
    if request.url.path == "/v1/boards/stripe/jobs/1":
        return httpx.Response(200, json={
            "id": 1,
            "content": "&lt;p&gt;Build things.&lt;/p&gt;",
            "pay_input_ranges": [{"min_cents": 12000000, "max_cents": 16000000, "currency_type": "USD"}],
        })
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



async def test_save_board_inserts_then_updates_without_duplicates(session):
    jobs = [
        gh.BoardJob(id=1, title="Backend", absolute_url="https://x/1"),
        gh.BoardJob(id=2, title="Data", absolute_url="https://x/2"),
    ]
    assert await gh.save_board(session, "stripe", jobs) == 2      # 2 new

    jobs[0] = gh.BoardJob(id=1, title="Senior Backend", absolute_url="https://x/1")
    assert await gh.save_board(session, "stripe", jobs) == 0      # 0 new, 1 updated

    rows = (await session.execute(select(Job).order_by(Job.external_id))).scalars().all()
    assert [r.title for r in rows] == ["Senior Backend", "Data"]

async def test_crawl_counts_each_outcome_and_saves_found_jobs(session):
    async with client() as c:
        summary = await gh.crawl(c, session, ["stripe", "notacompany", "broken"])

    assert summary == gh.CrawlSummary(found=1, missing=1, failed=1, new_jobs=1)


async def test_fetch_details_returns_clean_description_and_salary():
    async with client() as c:
        d = await gh.fetch_details(c, "stripe", 1)

    assert d.description == "Build things."
    assert (d.salary_min, d.salary_max, d.salary_currency) == (120000, 160000, "USD")
    assert d.content_html == "<p>Build things.</p>"
async def test_fill_descriptions_only_fetches_jobs_missing_one(session):
    session.add_all([
        Job(board="stripe", external_id=1, title="A"),                          # needs details
        Job(board="stripe", external_id=2, title="B", description="already"),   # skip
    ])
    await session.commit()

    calls = []
    def counting(request):
        calls.append(request.url.path)
        return fake_greenhouse(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(counting)) as c:
        first = await gh.fill_descriptions(c, session)
        second = await gh.fill_descriptions(c, session)

    assert (first, second) == (1, 0)
    assert calls == ["/v1/boards/stripe/jobs/1"]              # job 2 never fetched, nothing re-fetched
    job = (await session.execute(select(Job).where(Job.external_id == 1))).scalar_one()
    assert job.description == "Build things."
    assert job.salary_min == 120000