"""Two rematches of one user at once (double click, or a click during the nightly run) must not collide.

Uses real, committed rows on separate connections: the per-test savepoint session can't show a race."""
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.db_core import SessionLocal
from app.db.models_db import Job, MatchScore, Resume, User
from app.services.matching_services import match_all

pytestmark = pytest.mark.asyncio


async def test_concurrent_rematches_of_one_user_dont_crash():
    tag = uuid4().hex[:8]
    user = User(id=uuid4(), email=f"{tag}@race.test", hashed_password="x")
    jobs = [Job(title=f"Backend Engineer {i}", board=f"race{tag}-{i}", skills=["Python"], requirements=["Python"])
            for i in range(30)]
    async with SessionLocal() as s:
        s.add_all([user, *jobs])
        await s.flush()
        resume = Resume(user_id=user.id, skills=["Python"])
        s.add(resume)
        await s.commit()
    try:
        async def one():
            async with SessionLocal() as s:
                return await match_all(s, user_id=user.id)

        results = await asyncio.gather(*(one() for _ in range(4)), return_exceptions=True)
        assert not [r for r in results if isinstance(r, Exception)], results
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume.id))
            await s.execute(delete(Resume).where(Resume.id == resume.id))
            await s.execute(delete(Job).where(Job.board.like(f"race{tag}-%")))
            await s.execute(delete(User).where(User.id == user.id))
            await s.commit()


async def test_two_uploads_at_once_leave_exactly_one_resume():
    """resumes.user_id is UNIQUE: without the user-row lock one of these raised IntegrityError."""
    from sqlalchemy import select
    from app.services import resumes_services
    user = User(id=uuid4(), email=f"{uuid4().hex[:8]}@race.test", hashed_password="x")
    async with SessionLocal() as s:
        s.add(user)
        await s.commit()
    try:
        async def one(text):
            async with SessionLocal() as s:
                return await resumes_services.create(s, user.id, "cv.txt", text)

        results = await asyncio.gather(*(one(f"Python {i}".encode()) for i in range(4)), return_exceptions=True)
        assert not [r for r in results if isinstance(r, Exception)], results
        async with SessionLocal() as s:
            assert len((await s.scalars(select(Resume).where(Resume.user_id == user.id))).all()) == 1
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(User).where(User.id == user.id))     # resume goes with it (CASCADE)
            await s.commit()
