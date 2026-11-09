from uuid import uuid4
from app.core.security_core import create_access_token
from app.db.models_db import Job, Resume, MatchScore


async def test_dashboard_shows_only_my_matches_best_first(client, session):
    me, someone_else = uuid4(), uuid4()
    backend, data, frontend = Job(title="Backend"), Job(title="Data"), Job(title="Frontend")
    my_resume, their_resume = Resume(user_id=me), Resume(user_id=someone_else)
    session.add_all([backend, data, frontend, my_resume, their_resume])
    await session.flush()

    session.add_all([
        MatchScore(resume_id=my_resume.id,    job_id=data.id,     score=0.6),
        MatchScore(resume_id=my_resume.id,    job_id=backend.id,  score=0.9),
        MatchScore(resume_id=their_resume.id, job_id=frontend.id, score=0.99),
    ])
    await session.commit()

    headers = {"Authorization": f"Bearer {create_access_token(str(me))}"}
    r = await client.get("/dashboard", headers=headers)

    assert r.status_code == 200
    assert [m["title"] for m in r.json()] == ["Backend", "Data"]


async def test_dashboard_includes_met_and_missing(client, session):
    me = uuid4()
    job, resume = Job(title="Backend"), Resume(user_id=me)
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5,
                           detail={"met": ["Python"], "missing": ["Go"]}))
    await session.commit()

    r = await client.get("/dashboard", headers={"Authorization": f"Bearer {create_access_token(str(me))}"})

    assert r.json()[0]["detail"] == {"met": ["Python"], "missing": ["Go"]}

async def test_dashboard_includes_the_job_link(client, session):
    me = uuid4()
    job, resume = Job(title="Backend", url="https://x/1"), Resume(user_id=me)
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5))
    await session.commit()

    r = await client.get("/dashboard", headers={"Authorization": f"Bearer {create_access_token(str(me))}"})

    assert r.json()[0]["url"] == "https://x/1"


from app.db.models_db import Job as _J, MatchScore as _MS, Resume as _R


def _my_id(headers):
    """User id = the JWT's 'sub' claim (test-only: decode without verifying)."""
    import base64, json, uuid
    payload = headers["Authorization"].split()[1].split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return uuid.UUID(json.loads(base64.urlsafe_b64decode(payload))["sub"])


async def test_dashboard_sends_the_tier_label(client, auth_headers, session):
    job = _J(title="Backend Engineer", url="https://x/1")
    resume = _R(user_id=_my_id(auth_headers))
    session.add_all([job, resume])
    await session.flush()
    session.add(_MS(resume_id=resume.id, job_id=job.id, score=0.5, detail={"met": [], "missing": []}))
    await session.flush()
    body = (await client.get("/dashboard", headers=auth_headers)).json()
    assert body[0]["tier"] == "Strong match"


async def test_uploading_through_the_api_matches_immediately(client, auth_headers, session):
    session.add(_J(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("cv.txt", b"Python developer", "text/plain")})
    assert r.status_code == 201
    assert len((await client.get("/dashboard", headers=auth_headers)).json()) == 1
