from datetime import UTC
from uuid import uuid4

from app.core.security_core import create_access_token
from app.db.models_db import Job, MatchScore, Resume
from tests.conftest import user_row


async def test_dashboard_shows_only_my_matches_best_first(client, session):
    me = await _user(session)
    backend, data, frontend = Job(title="Backend"), Job(title="Data"), Job(title="Frontend")
    my_resume, their_resume = Resume(user_id=me), Resume(user=user_row())
    session.add_all([backend, data, frontend, my_resume, their_resume])
    await session.flush()

    session.add_all(
        [
            MatchScore(resume_id=my_resume.id, job_id=data.id, score=0.6),
            MatchScore(resume_id=my_resume.id, job_id=backend.id, score=0.9),
            MatchScore(resume_id=their_resume.id, job_id=frontend.id, score=0.99),
        ]
    )
    await session.commit()

    headers = {"Authorization": f"Bearer {create_access_token(str(me))}"}
    r = await client.get("/dashboard", headers=headers)

    assert r.status_code == 200
    assert [m["title"] for m in r.json()] == ["Backend", "Data"]


async def test_dashboard_includes_met_and_missing(client, session):
    me = await _user(session)
    job, resume = Job(title="Backend"), Resume(user_id=me)
    session.add_all([job, resume])
    await session.flush()
    session.add(
        MatchScore(
            resume_id=resume.id, job_id=job.id, score=0.5, detail={"met": ["Python"], "missing": ["Go"]}
        )
    )
    await session.commit()

    r = await client.get("/dashboard", headers={"Authorization": f"Bearer {create_access_token(str(me))}"})

    assert r.json()[0]["detail"] == {"met": ["Python"], "missing": ["Go"]}


async def test_dashboard_includes_the_job_link(client, session):
    me = await _user(session)
    job, resume = Job(title="Backend", url="https://x/1"), Resume(user_id=me)
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5))
    await session.commit()

    r = await client.get("/dashboard", headers={"Authorization": f"Bearer {create_access_token(str(me))}"})

    assert r.json()[0]["url"] == "https://x/1"


def _my_id(headers):
    import base64
    import json
    import uuid

    payload = headers["Authorization"].split()[1].split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return uuid.UUID(json.loads(base64.urlsafe_b64decode(payload))["sub"])


async def test_dashboard_sends_the_tier_label(client, auth_headers, session):
    job = Job(title="Backend Engineer", url="https://x/1")
    resume = Resume(user_id=_my_id(auth_headers))
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5, detail={"met": [], "missing": []}))
    await session.flush()
    body = (await client.get("/dashboard", headers=auth_headers)).json()
    assert body[0]["tier"] == "Strong match"


async def test_uploading_through_the_api_matches_immediately(client, auth_headers, session):
    session.add(Job(title="Backend Engineer", skills=["Python"]))
    await session.flush()
    r = await client.post(
        "/resumes", headers=auth_headers, files={"file": ("cv.txt", b"Python developer", "text/plain")}
    )
    assert r.status_code == 201
    assert len((await client.get("/dashboard", headers=auth_headers)).json()) == 1


async def test_dashboard_sends_the_years_note(client, auth_headers, session):
    job = Job(title="Backend Engineer", url="https://x/2")
    resume = Resume(user_id=_my_id(auth_headers))
    session.add_all([job, resume])
    await session.flush()
    session.add(
        MatchScore(
            resume_id=resume.id,
            job_id=job.id,
            score=0.5,
            detail={"met": [], "missing": [], "years_asked": 3, "over_years": True},
        )
    )
    await session.flush()
    assert (await client.get("/dashboard", headers=auth_headers)).json()[0][
        "years_note"
    ] == "asks for 3+ years"


async def test_dashboard_sends_company_and_location(client, auth_headers, session):
    job = Job(title="Backend Engineer", board="stripe", location="Remote, US", url="https://x/3")
    resume = Resume(user_id=_my_id(auth_headers))
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5, detail={"met": [], "missing": []}))
    await session.flush()
    m = (await client.get("/dashboard", headers=auth_headers)).json()[0]
    assert (m["company"], m["location"]) == ("stripe", "Remote, US")


async def _user(session):
    from datetime import datetime

    from app.db.models_db import User

    u = User(
        id=uuid4(),
        email=f"{uuid4().hex[:12]}@fixture.test",
        hashed_password="x",
        email_verified_at=datetime.now(UTC),
    )  # confirmed: can use resumes and matches
    session.add(u)
    await session.flush()
    return u.id


async def test_dashboard_shows_the_real_company_name(client, auth_headers, session):
    from app.db.models_db import Board

    session.add(Board(slug="a3c41b8b71eff8c4", name="Ivanti"))
    job = Job(title="Backend Engineer", board="a3c41b8b71eff8c4", location="Remote, US", url="https://x/9")
    resume = Resume(user_id=_my_id(auth_headers))
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5, detail={"met": [], "missing": []}))
    await session.flush()
    assert (await client.get("/dashboard", headers=auth_headers)).json()[0]["company"] == "Ivanti"
