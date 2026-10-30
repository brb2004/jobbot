from uuid import uuid4
from sqlalchemy import select
from app.db.models_db import Job, Resume, MatchScore
from app.llm.scorer_llm import LLMError
from app.services import scoring_services as scoring


class FakeExtractor:
    def __init__(self, mapping=None, default=("Python",)):
        self.mapping = mapping or {}
        self.default = list(default)
        self.calls = 0

    async def extract(self, text):
        self.calls += 1
        return self.mapping.get(text, self.default)


class BrokenExtractor:
    async def extract(self, text):
        raise LLMError("nonsense")


class FakeEmbedder:
    """Every distinct term gets its own direction, so only exact terms ever match."""
    def __init__(self):
        self.index = {}

    async def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * 64
            v[self.index.setdefault(t, len(self.index))] = 1.0
            out.append(v)
        return out


async def test_scores_by_matching_extracted_lists(session):
    session.add_all([
        Job(title="Backend", description="python and go"),
        Resume(user_id=uuid4(), raw_text="python developer"),
    ])
    await session.commit()
    ex = FakeExtractor({"python and go": ["Python", "Go"], "python developer": ["Python"]})

    assert await scoring.score_new(session, ex, FakeEmbedder()) == 1

    row = (await session.execute(select(MatchScore))).scalar_one()
    assert row.score == 0.5
    assert row.detail == {"met": ["Python"], "missing": ["Go"], "evidence": {"Python": "Python"}}


async def test_never_scores_or_extracts_twice(session):
    session.add_all([Job(title="Python", description="python"), Resume(user_id=uuid4(), raw_text="python")])
    await session.commit()
    ex, emb = FakeExtractor(), FakeEmbedder()

    await scoring.score_new(session, ex, emb)
    calls_after_first = ex.calls
    second = await scoring.score_new(session, ex, emb)

    assert second == 0
    assert ex.calls == calls_after_first


async def test_only_shortlisted_jobs_get_extracted(session):
    session.add_all([
        Job(title="Python Postgres", description="python postgres fastapi"),
        Job(title="Python", description="python postgres"),
        Job(title="Python only", description="python"),
        Job(title="Sales", description="cold calling"),
        Resume(user_id=uuid4(), raw_text="python postgres fastapi"),
    ])
    await session.commit()
    ex = FakeExtractor()

    await scoring.score_new(session, ex, FakeEmbedder(), k=2)

    assert ex.calls == 3                  # 1 resume + the 2 shortlisted jobs, never the other 2


async def test_failed_extraction_scores_nothing_and_does_not_crash(session):
    session.add_all([Job(title="Python", description="python"), Resume(user_id=uuid4(), raw_text="python")])
    await session.commit()

    assert await scoring.score_new(session, BrokenExtractor(), FakeEmbedder()) == 0
    assert (await session.execute(select(MatchScore))).scalars().all() == []
