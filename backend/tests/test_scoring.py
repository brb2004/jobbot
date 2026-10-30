from uuid import uuid4
from sqlalchemy import select
from app.db.models_db import Job, Resume, MatchScore
from app.llm.scorer_llm import LLMError, ScoreResult
from app.services import scoring_services as scoring


class FakeLLM:
    def __init__(self, score=0.75):
        self.score_value = score
        self.calls = 0

    async def score(self, resume, job) -> ScoreResult:
        self.calls += 1
        return ScoreResult(score=self.score_value, met=["Python"], missing=["Go"],
                           evidence={"Python": "Built APIs in Python"})


class BrokenLLM:
    async def score(self, resume, job):
        raise LLMError("model said nonsense")


async def test_scores_resumes_against_matching_jobs(session):
    session.add_all([
        Job(title="Python A", description="python"),
        Job(title="Python B", description="python"),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()

    n = await scoring.score_new(session, FakeLLM())

    assert n == 2
    rows = (await session.execute(select(MatchScore))).scalars().all()
    assert [r.score for r in rows] == [0.75, 0.75]


async def test_stores_met_and_missing_with_the_score(session):
    session.add_all([Job(title="Python", description="python"), Resume(user_id=uuid4(), raw_text="python")])
    await session.commit()

    await scoring.score_new(session, FakeLLM())

    row = (await session.execute(select(MatchScore))).scalar_one()
    assert row.detail == {"met": ["Python"], "missing": ["Go"],
                          "evidence": {"Python": "Built APIs in Python"}}


async def test_never_scores_the_same_pair_twice(session):
    session.add_all([Job(title="Python", description="python"), Resume(user_id=uuid4(), raw_text="python")])
    await session.commit()
    llm = FakeLLM()

    await scoring.score_new(session, llm)
    second_run = await scoring.score_new(session, llm)

    assert second_run == 0
    assert llm.calls == 1


async def test_only_top_k_jobs_reach_the_llm(session):
    session.add_all([
        Job(title="Python Postgres", description="python postgres fastapi"),
        Job(title="Python", description="python postgres"),
        Job(title="Python only", description="python"),
        Job(title="Sales", description="cold calling"),
        Resume(user_id=uuid4(), raw_text="python postgres fastapi"),
    ])
    await session.commit()
    llm = FakeLLM()

    await scoring.score_new(session, llm, k=2)

    assert llm.calls == 2


async def test_bad_llm_output_skips_the_pair_without_crashing(session):
    session.add_all([Job(title="Python", description="python"), Resume(user_id=uuid4(), raw_text="python")])
    await session.commit()

    assert await scoring.score_new(session, BrokenLLM()) == 0
    assert (await session.execute(select(MatchScore))).scalars().all() == []