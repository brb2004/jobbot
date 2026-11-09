import uuid

from sqlalchemy import select

from app.db.models_db import Job, MatchScore, Resume, User
from app.services.skills_services import default_tagger
from app.services.matching_services import match_all, tag_jobs, tag_resumes


async def test_tag_jobs_fills_skills_once(session):
    new = Job(title="A", requirements=["3+ years of Go", "Postgres experience"])
    done = Job(title="B", requirements=["Go"], skills=["Rust"], skills_version=default_tagger().version)
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


async def test_match_all_credits_implied_skills(session):
    job = Job(title="AI Engineer", skills=["AI"])
    resume = Resume(user_id=uuid.uuid4(), skills=["LLM"])           # skills.txt: LLM > ... > AI
    session.add_all([job, resume])
    await session.flush()
    await match_all(session)
    row = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).one()
    assert row.detail["met"] == ["AI"]


async def test_match_all_sinks_jobs_asking_for_too_many_years(session):
    user = User(id=uuid.uuid4(), email="y@match.com", hashed_password="x", preferences={"years_experience": 1})
    senior_ask = Job(title="Engineer A", skills=["Python"], requirements=["5+ years of Python"])
    fair_ask = Job(title="Engineer B", skills=["Python"], requirements=["Python"])
    resume = Resume(user_id=user.id, skills=["Python"])
    session.add_all([user, senior_ask, fair_ask, resume])
    await session.flush()
    await match_all(session)
    rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id)
                                  .order_by(MatchScore.score.desc()))).all()
    assert [r.job_id for r in rows] == [fair_ask.id, senior_ask.id]   # still shown, just lower
    assert rows[1].detail["years_asked"] == 5


async def test_extra_skills_from_preferences_count_like_resume_skills(session):
    user = User(id=uuid.uuid4(), email="x@match.com", hashed_password="x",
                preferences={"extra_skills": ["k8s", "not-a-real-skill"]})
    job = Job(title="Platform Engineer", skills=["Kubernetes"])
    resume = Resume(user_id=user.id, skills=["Python"])
    session.add_all([user, job, resume])
    await session.flush()
    await match_all(session)
    row = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).one()
    assert row.detail["met"] == ["Kubernetes"]


from app.services.skills_services import Tagger


async def test_jobs_are_retagged_when_the_taxonomy_changes(session):
    job = Job(title="E", requirements=["Go and Rust"])
    session.add(job)
    v1, v2 = Tagger.from_text("Go"), Tagger.from_text("Go\nRust")
    assert v1.version != v2.version
    await tag_jobs(session, v1)
    assert job.skills == ["Go"]
    assert await tag_jobs(session, v2) == 1             # stale -> re-tagged
    assert job.skills == ["Go", "Rust"]
    assert await tag_jobs(session, v2) == 0             # current -> untouched


async def test_resumes_are_retagged_when_the_taxonomy_changes(session):
    r = Resume(user_id=uuid.uuid4(), raw_text="Go and Rust")
    session.add(r)
    await tag_resumes(session, Tagger.from_text("Go"))
    await tag_resumes(session, Tagger.from_text("Go\nRust"))
    assert r.skills == ["Go", "Rust"]


async def test_match_all_for_one_user_leaves_everyone_else_alone(session):
    job = Job(title="Engineer", skills=["Python"])
    mine = Resume(user_id=uuid.uuid4(), skills=["Python"])
    theirs = Resume(user_id=uuid.uuid4(), skills=["Python"])
    session.add_all([job, mine, theirs])
    await session.flush()
    session.add(MatchScore(resume_id=theirs.id, job_id=job.id, score=0.99, detail={}))   # someone else's old row
    await session.flush()
    await match_all(session, user_id=mine.user_id)
    my_rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == mine.id))).all()
    their_rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == theirs.id))).all()
    assert len(my_rows) == 1
    assert [r.score for r in their_rows] == [0.99]                                        # untouched


async def test_same_role_posted_per_location_shows_once(session):
    a = Job(title="Backend Engineer", board="stripe", external_id=1, skills=["Python"], location="NYC")
    b = Job(title="Backend Engineer ", board="stripe", external_id=2, skills=["Python"], location="SF")
    resume = Resume(user_id=uuid.uuid4(), skills=["Python"])
    session.add_all([a, b, resume])
    await session.flush()
    await match_all(session)
    rows = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).all()
    assert len(rows) == 1


async def test_senior_title_without_a_number_counts_as_5_years(session):
    user = User(id=uuid.uuid4(), email="sr@match.com", hashed_password="x", preferences={"years_experience": 0})
    job = Job(title="Senior Backend Engineer", skills=["Python"], requirements=["Python"])
    resume = Resume(user_id=user.id, skills=["Python"])
    session.add_all([user, job, resume])
    await session.flush()
    await match_all(session)
    d = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).one().detail
    assert (d["years_asked"], d["years_source"], d["over_years"]) == (5, "title", True)


async def test_detected_years_apply_when_the_user_left_years_blank(session):
    user = User(id=uuid.uuid4(), email="det@match.com", hashed_password="x", preferences={})
    job = Job(title="Backend Engineer", skills=["Python"], requirements=["5+ years of Python"])
    resume = Resume(user_id=user.id, skills=["Python"], years_detected=1)
    session.add_all([user, job, resume])
    await session.flush()
    await match_all(session)
    d = (await session.scalars(select(MatchScore).where(MatchScore.resume_id == resume.id))).one().detail
    assert d["over_years"] is True
