from uuid import uuid4
from app.core.security import create_access_token

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