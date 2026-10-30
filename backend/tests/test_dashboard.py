from uuid import uuid4
from app.core.security import create_access_token
from app.db.models import Job, Resume, MatchScore

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