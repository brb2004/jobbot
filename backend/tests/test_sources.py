import httpx
from sqlalchemy import select

from app.db.models_db import Board, Job
from app.ingest import ashby_ingest, crawl_ingest, lever_ingest
from app.ingest import greenhouse_ingest as gh
from app.ingest.ashby_ingest import ASHBY
from app.ingest.crawl_ingest import crawl_source, name_from_slug, remote_location, retire_dropped
from app.ingest.lever_ingest import LEVER
from app.services.extraction_services import fill_job_requirements
from app.services.locations_services import location_ok
from app.services.preferences_services import Preferences

REQS = "<h2>What you'll bring</h2><ul><li>3+ years of Python</li><li>PostgreSQL</li></ul>"


def ashby_job(id="a1b2c3d4-0000-4000-8000-000000000001", **kw):
    return {
        "id": id,
        "title": "Backend Engineer",
        "location": "United States",
        "secondaryLocations": [],
        "isListed": True,
        "isRemote": True,
        "workplaceType": "Remote",
        "jobUrl": f"https://jobs.ashbyhq.com/acme/{id}",
        "applyUrl": f"https://jobs.ashbyhq.com/acme/{id}/application",
        "descriptionHtml": "<p>About us</p>" + REQS,
        "descriptionPlain": "About us",
        "compensation": {
            "summaryComponents": [
                {
                    "compensationType": "Salary",
                    "interval": "1 YEAR",
                    "currencyCode": "USD",
                    "minValue": 150000,
                    "maxValue": 190000,
                },
                {
                    "compensationType": "EquityPercentage",
                    "interval": "NONE",
                    "minValue": 0.1,
                    "maxValue": 0.5,
                },
            ]
        },
        **kw,
    }


def lever_job(id="5ac21346-8e0c-4494-8e7a-3eb92ff77902", **kw):
    return {
        "id": id,
        "text": "Software Engineer",
        "hostedUrl": f"https://jobs.lever.co/acme/{id}",
        "applyUrl": f"https://jobs.lever.co/acme/{id}/apply",
        "categories": {
            "location": "Dallas, TX",
            "allLocations": ["Dallas, TX", "Austin, TX"],
            "team": "Engineering",
            "commitment": "Full-time",
        },
        "description": "<div>Join us.</div>",
        "lists": [
            {"text": "Requirements", "content": "<li>Go or Rust</li><li>Kubernetes</li>"},
            {"text": "Benefits", "content": "<li>Health insurance</li>"},
        ],
        "additional": "<div>We are an equal opportunity employer.</div>",
        "workplaceType": "hybrid",
        "salaryRange": {"currency": "USD", "interval": "per-year-salary", "min": 120000, "max": 160000},
        **kw,
    }


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def rows(session, board):
    return (
        await session.scalars(
            select(Job)
            .where(Job.board == board)
            .order_by(Job.external_id)
            .execution_options(populate_existing=True)
        )
    ).all()


# ---- shared helpers ----


def test_remote_locations_say_remote_so_preferences_read_them():
    assert remote_location(["United States", "Canada"], True) == "Remote - United States; Remote - Canada"
    assert remote_location(["Remote (US)"], True) == "Remote (US)"  # already says it
    assert remote_location([], True) == "Remote"
    assert remote_location(["Dallas, TX", "Dallas, TX", " "], False) == "Dallas, TX"
    assert remote_location([], False) is None


def test_a_remote_us_posting_reaches_a_dfw_user():
    dfw = Preferences(locations=["Dallas-Fort Worth"])
    assert location_ok(remote_location(["United States"], True), dfw)
    assert not location_ok(
        remote_location(["United States"], True), Preferences(locations=["Dallas-Fort Worth"], remote=False)
    )


def test_names_from_slugs():
    assert name_from_slug("acme-corp") == "Acme Corp"
    assert name_from_slug("openai") == "Openai"


# ---- Ashby ----


def ashby_handler(jobs, status=200):
    def handler(req):
        assert req.url.params["includeCompensation"] == "true"
        if req.url.path == "/posting-api/job-board/acme":
            return httpx.Response(status, json={"apiVersion": "1", "jobs": jobs})
        return httpx.Response(404, json={})

    return handler


async def test_ashby_board_saves_full_postings_under_a_namespaced_key(session):
    async with client(ashby_handler([ashby_job()])) as c:
        summary = await crawl_source(c, session, ASHBY, ["acme", "nobody"])
    assert (summary.found, summary.missing, summary.new_jobs) == (1, 1, 1)
    [job] = await rows(session, "ashby:acme")
    assert job.title == "Backend Engineer"
    assert job.location == "Remote - United States"
    assert job.url.startswith("https://jobs.ashbyhq.com/acme/")
    assert (job.salary_min, job.salary_max, job.salary_currency) == (150000, 190000, "USD")
    assert "3+ years of Python" in job.description and job.content_html.startswith("<p>About us")
    assert (await session.get(Board, "ashby:acme")).name == "Acme"
    await fill_job_requirements(session)  # same extraction path as Greenhouse
    assert (await rows(session, "ashby:acme"))[0].requirements == ["3+ years of Python", "PostgreSQL"]


async def test_ashby_secondary_locations_and_onsite():
    p = ashby_ingest.posting(
        ashby_job(
            isRemote=False,
            workplaceType="OnSite",
            location="New York",
            secondaryLocations=[{"location": "Dallas"}, {"location": "New York"}],
        )
    )
    assert p.location == "New York; Dallas"


async def test_ashby_hourly_pay_is_not_a_salary():
    p = ashby_ingest.posting(
        ashby_job(
            compensation={
                "summaryComponents": [
                    {
                        "compensationType": "Salary",
                        "interval": "1 HOUR",
                        "currencyCode": "USD",
                        "minValue": 40,
                        "maxValue": 60,
                    }
                ]
            }
        )
    )
    assert (p.salary_min, p.salary_max) == (None, None)


async def test_ashby_unlisted_postings_close_and_malformed_ones_dont(session):
    a, b, broken = (ashby_job(id=f"id-{n}") for n in "abc")
    async with client(ashby_handler([a, b, broken])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    del broken["title"]  # malformed now: skipped, still listed
    async with client(ashby_handler([a, {**b, "isListed": False}, broken])) as c:
        summary = await crawl_source(c, session, ASHBY, ["acme"])
    state = {j.external_id: j.closed_at is None for j in await rows(session, "ashby:acme")}
    assert state == {"id-a": True, "id-b": False, "id-c": True}
    assert summary.closed == 1


async def test_ashby_bad_response_fails_the_board_and_closes_nothing(session):
    async with client(ashby_handler([ashby_job()])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    async with client(lambda req: httpx.Response(200, text="<html>down</html>")) as c:
        summary = await crawl_source(c, session, ASHBY, ["acme"])
    assert summary.failed == 1
    assert (await rows(session, "ashby:acme"))[0].closed_at is None


async def test_unchanged_posting_keeps_its_requirements_edited_one_rebuilds(session):
    async with client(ashby_handler([ashby_job()])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    await fill_job_requirements(session)
    async with client(ashby_handler([ashby_job(title="Backend Engineer II")])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])  # same text, new title
    [job] = await rows(session, "ashby:acme")
    assert job.title == "Backend Engineer II" and job.requirements == ["3+ years of Python", "PostgreSQL"]

    edited = ashby_job(descriptionHtml="<h2>Requirements</h2><ul><li>Terraform</li></ul>")
    async with client(ashby_handler([edited])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    [job] = await rows(session, "ashby:acme")
    assert job.requirements is None and job.skills_version is None and "Terraform" in job.description
    await fill_job_requirements(session)
    assert (await rows(session, "ashby:acme"))[0].requirements == ["Terraform"]


async def test_a_reopened_posting_gets_its_pruned_text_back(session):
    async with client(ashby_handler([ashby_job()])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    [job] = await rows(session, "ashby:acme")
    job.content_html, job.description = None, None  # what prune does to old closed jobs
    await session.commit()
    async with client(ashby_handler([ashby_job()])) as c:
        await crawl_source(c, session, ASHBY, ["acme"])
    assert (await rows(session, "ashby:acme"))[0].content_html.startswith("<p>About us")


# ---- Lever ----


def lever_handler(jobs):
    def handler(req):
        assert req.url.params["mode"] == "json"
        if req.url.path != "/v0/postings/acme":
            return httpx.Response(404, json={"ok": False, "error": "Document not found"})
        skip, limit = int(req.url.params["skip"]), int(req.url.params["limit"])
        return httpx.Response(200, json=jobs[skip : skip + limit])

    return handler


async def test_lever_pages_through_a_site(session, monkeypatch):
    monkeypatch.setattr(lever_ingest, "PAGE", 2)
    jobs = [lever_job(id=f"id-{n}", text=f"Engineer {n}") for n in range(5)]
    async with client(lever_handler(jobs)) as c:
        summary = await crawl_source(c, session, LEVER, ["acme", "ghost"])
    assert (summary.found, summary.missing, summary.new_jobs) == (1, 1, 5)
    assert len(await rows(session, "lever:acme")) == 5


async def test_lever_that_ignores_paging_isnt_read_forever(session, monkeypatch):
    monkeypatch.setattr(lever_ingest, "PAGE", 2)
    jobs = [lever_job(id=f"id-{n}") for n in range(3)]
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=jobs)  # same full list whatever skip says

    async with client(handler) as c:
        got, ids = await lever_ingest.fetch_board(c, "acme")
    assert len(ids) == 3 and len(calls) == 2


async def test_lever_lists_become_headed_sections(session):
    async with client(lever_handler([lever_job()])) as c:
        await crawl_source(c, session, LEVER, ["acme"])
    [job] = await rows(session, "lever:acme")
    assert job.location == "Dallas, TX; Austin, TX"  # hybrid: not remote
    assert (job.salary_min, job.salary_max) == (120000, 160000)
    await fill_job_requirements(session)
    assert (await rows(session, "lever:acme"))[0].requirements == ["Go or Rust", "Kubernetes"]


async def test_lever_remote_and_non_yearly_pay():
    p = lever_ingest.posting(
        lever_job(
            workplaceType="remote",
            categories={"location": "United States"},
            salaryRange={"currency": "USD", "interval": "per-hour-wage", "min": 40, "max": 60},
        )
    )
    assert p.location == "Remote - United States"
    assert p.salary_min is None


# ---- across sources ----


async def test_same_slug_and_id_on_two_sources_stay_separate(session):
    gh_job = {"id": 1, "title": "Engineer", "absolute_url": "https://gh/1"}

    def greenhouse(req):
        return httpx.Response(
            200, json={"jobs": [gh_job]} if req.url.path.endswith("/jobs") else {"name": "Acme Inc"}
        )

    async with client(greenhouse) as c:
        await gh.crawl(c, session, ["acme"])
    async with client(lever_handler([lever_job(id="1")])) as c:
        await crawl_source(c, session, LEVER, ["acme"])
    assert [j.url for j in await rows(session, "acme")] == ["https://gh/1"]
    assert [j.url for j in await rows(session, "lever:acme")] == ["https://jobs.lever.co/acme/1"]
    assert (await session.get(Board, "acme")).name == "Acme Inc"


async def test_retire_dropped_keeps_every_listed_source(session):
    session.add_all(
        [
            Job(board="acme", external_id="1", title="A"),
            Job(board="ashby:acme", external_id="x", title="B"),
            Job(board="lever:gone", external_id="y", title="C"),
        ]
    )
    await session.commit()
    assert await retire_dropped(session, ["acme", "ashby:acme"]) == 1
    assert (await rows(session, "lever:gone"))[0].closed_at is not None


async def test_greenhouse_details_run_skips_other_sources(session):
    session.add(Job(board="ashby:acme", external_id="x", title="B"))  # no description, but not Greenhouse
    await session.commit()

    def handler(req):
        raise AssertionError(f"should not fetch {req.url}")

    async with client(handler) as c:
        assert await gh.fill_descriptions(c, session) == 0


def test_backoff_lives_in_the_shared_core():
    assert crawl_ingest.BACKOFF == 0  # conftest disables waits for every source
