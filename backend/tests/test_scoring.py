from uuid import uuid4
from sqlalchemy import select
from app.db.models_db import Job, Resume, MatchScore
from app.services import scoring_services as scoring


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