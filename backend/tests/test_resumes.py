from uuid import uuid4
from app.core.security_core import create_access_token


async def test_upload_resume_then_list_it(client, auth_headers):
    files = {"file": ("resume.txt", b"Python, FastAPI, Postgres, Kubernetes", "text/plain")}

    up = await client.post("/resumes", files=files, headers=auth_headers)
    assert up.status_code == 201

    listed = await client.get("/resumes", headers=auth_headers)
    assert [r["filename"] for r in listed.json()] == ["resume.txt"]

def headers_for(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def test_cannot_see_another_users_resumes(client):
    alice, bob = headers_for(uuid4()), headers_for(uuid4())
    await client.post("/resumes", files={"file": ("alice.txt", b"secret", "text/plain")}, headers=alice)

    r = await client.get("/resumes", headers=bob)

    assert r.json() == []


async def test_rejects_files_over_2mb(client, auth_headers):
    big = b"x" * (2 * 1024 * 1024 + 1)
    r = await client.post("/resumes", files={"file": ("big.txt", big, "text/plain")}, headers=auth_headers)
    assert r.status_code == 413


async def test_rejects_unsupported_file_types(client, auth_headers):
    r = await client.post("/resumes", files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
                          headers=auth_headers)
    assert r.status_code == 415