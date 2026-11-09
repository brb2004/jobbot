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

import uuid as _uuid

from sqlalchemy import select as _select

from app.db.models_db import Job as _Job, MatchScore as _MatchScore, Resume as _Resume
from app.services import resumes_services as _resumes


async def test_uploading_again_replaces_the_previous_resume_and_its_scores(session):
    me, other = _uuid.uuid4(), _uuid.uuid4()
    first = await _resumes.create(session, me, "a.txt", b"Python")
    theirs = await _resumes.create(session, other, "t.txt", b"Rust")
    job = _Job(title="E")
    session.add(job)
    await session.flush()
    session.add(_MatchScore(resume_id=first.id, job_id=job.id, score=0.5, detail={}))
    await session.flush()

    second = await _resumes.create(session, me, "b.txt", b"Go")

    mine = (await session.scalars(_select(_Resume).where(_Resume.user_id == me))).all()
    assert [(r.id, r.raw_text) for r in mine] == [(second.id, "Go")]
    assert (await session.scalars(_select(_MatchScore).where(_MatchScore.resume_id == first.id))).all() == []
    assert (await session.get(_Resume, theirs.id)) is not None          # other users untouched


async def test_upload_matches_the_user_immediately(session):
    me = _uuid.uuid4()
    session.add(_Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    resume = await _resumes.upload(session, me, "cv.txt", b"Python developer")
    rows = (await session.scalars(_select(_MatchScore).where(_MatchScore.resume_id == resume.id))).all()
    assert len(rows) == 1
