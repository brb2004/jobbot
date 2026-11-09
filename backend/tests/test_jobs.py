from uuid import uuid4
from app.core.security_core import create_access_token
from app.db.models_db import Job

async def test_get_job_requires_auth(client):
    r = await client.get(f"/jobs/{uuid4()}")
    assert r.status_code == 401

async def test_get_job_rejects_bad_token(client):
    r = await client.get(f"/jobs/{uuid4()}", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_get_missing_job_returns_404(client, auth_headers):
    r = await client.get(f"/jobs/{uuid4()}", headers=auth_headers)
    assert r.status_code == 404



async def test_list_jobs_returns_saved_jobs(client, session, auth_headers):
    session.add_all([Job(title="Backend Engineer"), Job(title="Data Engineer")])
    await session.commit()

    r = await client.get("/jobs", headers=auth_headers)

    assert r.status_code == 200
    assert {j["title"] for j in r.json()} == {"Backend Engineer", "Data Engineer"}

from datetime import datetime as _dt, timezone as _tz

from app.db.models_db import Job as _Job


async def test_jobs_list_is_paged_and_hides_closed(client, auth_headers, session):
    session.add_all([_Job(title=f"Open {i}") for i in range(3)] +
                    [_Job(title="Gone", closed_at=_dt.now(_tz.utc))])
    await session.flush()
    titles = [j["title"] for j in (await client.get("/jobs?limit=2", headers=auth_headers)).json()]
    assert len(titles) == 2 and "Gone" not in titles
    rest = [j["title"] for j in (await client.get("/jobs?limit=2&offset=2", headers=auth_headers)).json()]
    assert "Gone" not in rest


async def test_jobs_paging_limits_are_enforced(client, auth_headers):
    assert (await client.get("/jobs?limit=1000000", headers=auth_headers)).status_code == 422
    assert (await client.get("/jobs?offset=-1", headers=auth_headers)).status_code == 422
