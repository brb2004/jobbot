import uuid

from sqlalchemy import select

from app.db.models_db import Job, MatchScore, Resume, User
from app.services.matching_services import match_all, tag_jobs, tag_resumes


async def test_tag_jobs_fills_skills_once(session):
    new = Job(title="A", requirements=["3+ years of Go", "Postgres experience"])
    done = Job(title="B", requirements=["Go"], skills=["Rust"])
    session.add_all([new, done])
    await tag_jobs(session)
    assert new.skills == ["Go", "PostgreSQL"]
    assert done.skills == ["Rust"]                       # already tagged: untouched


async def test_tag_resumes_uses_the_taxonomy(session):
    r = Resume(user_id=uuid.uuid4(), raw_text="Python, Docker and k8s")
    session.add(r)
    await tag_resumes(session)
    assert r.skills == ["Docker", "Kubernetes", "Python"]


async def test_match_all_respects_preferences_and_replaces_old_scores(session):
    user = User(id=uuid.uuid4(), email="m@match.com", hashed_password="x",
                preferences={"exclude_titles": ["senior"]})
    fit = Job(title="Backend Engineer", skills=["Python", "Kubernetes"])
    senior = Job(title="Senior Backend Engineer", skills=["Python"])
    unrelated = Job(title="Data Engineer", skills=["Rust"])
    resume = Resume(user_id=user.id, skills=["Python"])
    session.add_all([user, fit, senior, unrelated, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=unrelated.id, score=0.9, detail={}))   # stale
    await session.flush()

    await match_all(session)

    rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).all()
    assert [r.job_id for r in rows] == [fit.id]          # senior filtered, unrelated shares nothing, stale gone
    assert rows[0].detail["met"] == ["Python"]
    assert rows[0].detail["missing"] == ["Kubernetes"]
    assert 0 < rows[0].score < 0.5                       # Kubernetes is rarer, so it outweighs Python
