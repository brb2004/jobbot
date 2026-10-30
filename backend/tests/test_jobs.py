from uuid import uuid4
from app.core.security import create_access_token
from app.db.models import Job

async def test_get_job_requires_auth(client):
    r = await client.get(f"/jobs/{uuid4()}")
    assert r.status_code == 401

async def test_get_job_rejects_bad_token(client):
    r = await client.get(f"/jobs/{uuid4()}", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_get_missing_job_returns_404(client):
    token = create_access_token(str(uuid4()))
    r = await client.get(f"/jobs/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404



async def test_list_jobs_returns_saved_jobs(client, session, auth_headers):
    session.add_all([Job(title="Backend Engineer"), Job(title="Data Engineer")])
    await session.commit()

    r = await client.get("/jobs", headers=auth_headers)

    assert r.status_code == 200
    assert {j["title"] for j in r.json()} == {"Backend Engineer", "Data Engineer"}