from uuid import uuid4
from sqlalchemy import select
from app.db.models_db import Job, Resume, MatchScore
from app.services import scoring_services as scoring
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import true, and_


class FakeLLM:
    """Stands in for the real model. Counts calls so tests can check we don't waste any."""
    def __init__(self, score=0.75):
        self.score_value = score
        self.calls = 0

    async def score(self, resume, job) -> float:
        self.calls += 1
        return self.score_value


async def test_scores_every_unscored_pair(session):
    session.add_all([Job(title="A"), Job(title="B"), Resume(user_id=uuid4())])
    await session.commit()

    n = await scoring.score_new(session, FakeLLM())

    assert n == 2
    rows = (await session.execute(select(MatchScore))).scalars().all()
    assert [r.score for r in rows] == [0.75, 0.75]


async def test_never_scores_the_same_pair_twice(session):
    session.add_all([Job(title="A"), Resume(user_id=uuid4())])
    await session.commit()
    llm = FakeLLM()

    await scoring.score_new(session, llm)
    second_run = await scoring.score_new(session, llm)

    assert second_run == 0
    assert llm.calls == 1



async def unscored_pairs(s: AsyncSession) -> list[tuple[Resume, Job]]:
    stmt = (
        select(Resume, Job)
        .join(Job, true())                                    # cross join: every resume × every job
        .outerjoin(MatchScore, and_(
            MatchScore.resume_id == Resume.id,
            MatchScore.job_id == Job.id,
        ))
        .where(MatchScore.id.is_(None))                       # anti-join: no score yet
    )
    return list((await s.execute(stmt)).all())


async def score_new(s: AsyncSession, llm) -> int:
    pairs = await unscored_pairs(s)
    for resume, job in pairs:
        score = await llm.score(resume, job)
        s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=score))
    await s.commit()
    return len(pairs)