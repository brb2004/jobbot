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


async def test_cannot_see_another_users_resumes(client, session):
    alice, bob = headers_for(await _user(session)), headers_for(await _user(session))
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


async def _setup_with_one_match(client, auth_headers, session):
    session.add(_Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("cv.txt", b"Python developer", "text/plain")})
    assert r.status_code == 201
    assert len((await client.get("/dashboard", headers=auth_headers)).json()) == 1


async def test_empty_file_is_rejected_and_keeps_the_old_resume(client, auth_headers, session):
    await _setup_with_one_match(client, auth_headers, session)
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r.status_code == 422
    assert "text" in r.json()["detail"]
    assert len((await client.get("/dashboard", headers=auth_headers)).json()) == 1      # matches survived


async def test_file_with_no_skills_is_rejected_and_keeps_the_old_resume(client, auth_headers, session):
    await _setup_with_one_match(client, auth_headers, session)
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")})
    assert r.status_code == 422
    assert "skills" in r.json()["detail"]
    assert len((await client.get("/dashboard", headers=auth_headers)).json()) == 1


async def _user(session):
    """A real user row: tokens for users that don't exist are now rejected."""
    from datetime import datetime, timezone
    from app.db.models_db import User
    u = User(id=uuid4(), email=f"{uuid4().hex[:12]}@fixture.test", hashed_password="x",
             email_verified_at=datetime.now(timezone.utc))        # confirmed: can use resumes and matches
    session.add(u)
    await session.flush()
    return u.id


import io as _io
import zipfile as _zip


def _docx_with(document_xml: bytes) -> bytes:
    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w", _zip.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", document_xml)
    return buf.getvalue()


async def test_zip_bomb_docx_is_rejected_cleanly(client, auth_headers):
    bomb = _docx_with(b" " * (11 * 1024 * 1024))                 # ~11 MB unpacked, a few KB packed
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("big.docx", bomb, "application/octet-stream")})
    assert r.status_code == 422
    assert "too large" in r.json()["detail"]


async def test_corrupt_docx_is_422_not_500(client, auth_headers):
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("bad.docx", b"PK\x03\x04garbage", "application/octet-stream")})
    assert r.status_code == 422


async def test_filenames_are_sanitized(client, auth_headers, session):
    session.add(_Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    nasty = "../../etc/<img src=x onerror=alert(1)>" + "a" * 200 + ".txt"
    r = await client.post("/resumes", headers=auth_headers, files={"file": (nasty, b"Python developer", "text/plain")})
    assert r.status_code == 201
    name = (await client.get("/resumes", headers=auth_headers)).json()[0]["filename"]
    assert not any(c in name for c in "/\\<>") and name.endswith(".txt") and len(name) <= 100


async def test_upload_reports_detected_years(client, auth_headers, session):
    session.add(_Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    await client.post("/resumes", headers=auth_headers,
                      files={"file": ("cv.txt", b"Python developer with 3 years of experience", "text/plain")})
    assert (await client.get("/resumes", headers=auth_headers)).json()[0]["years_detected"] == 3
