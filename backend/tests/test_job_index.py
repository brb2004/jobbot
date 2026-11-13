from datetime import UTC
from uuid import uuid4

import pytest

from app.db.models_db import Job, Resume, User
from app.services import job_index_services as job_index
from app.services import matching_services as matching

pytestmark = pytest.mark.asyncio


async def _user_with_jobs(session, n=3):
    user = User(id=uuid4(), email=f"{uuid4().hex[:8]}@index.test", hashed_password="x")
    jobs = [
        Job(
            title=f"Backend Engineer {i}",
            board=f"idx{i}",
            skills=["Python"],
            requirements=["3+ years Python"],
        )
        for i in range(n)
    ]
    session.add_all([user, *jobs, Resume(user_id=user.id, skills=["Python"])])
    await session.flush()
    return user, jobs


async def test_the_index_is_built_once_and_reused(session, monkeypatch):
    user, _ = await _user_with_jobs(session)
    builds = []
    real = job_index.build_job_index
    monkeypatch.setattr(job_index, "build_job_index", lambda *a, **k: builds.append(1) or real(*a, **k))
    assert await matching.rematch_user(session, user.id) > 0
    assert await matching.rematch_user(session, user.id) > 0
    assert len(builds) == 1  # second rematch reused it


async def test_the_index_rebuilds_when_jobs_open_or_close(session, monkeypatch):
    user, jobs = await _user_with_jobs(session)
    await matching.rematch_user(session, user.id)
    first = job_index._cached
    session.add(Job(title="Platform Engineer", board="idxnew", skills=["Python"], requirements=["Python"]))
    await session.flush()
    await matching.rematch_user(session, user.id)
    assert job_index._cached is not first  # a new job: new fingerprint, rebuilt
    second = job_index._cached
    from datetime import datetime

    jobs[0].closed_at = datetime.now(UTC)
    await session.flush()
    await matching.rematch_user(session, user.id)
    assert job_index._cached is not second and jobs[0].id not in job_index._cached.skills


async def test_cached_and_fresh_rematches_agree(session):
    user, _ = await _user_with_jobs(session, n=5)
    from sqlalchemy import select

    from app.db.models_db import MatchScore

    async def mine():
        rows = (
            await session.execute(
                select(MatchScore.job_id, MatchScore.score, MatchScore.detail)
                .join(Resume, Resume.id == MatchScore.resume_id)
                .where(Resume.user_id == user.id)
            )
        ).all()
        return sorted((str(j), sc, str(d)) for j, sc, d in rows)

    await matching.match_all(session, user_id=user.id)
    fresh = await mine()
    await matching.rematch_user(session, user.id)
    assert await mine() == fresh and fresh
