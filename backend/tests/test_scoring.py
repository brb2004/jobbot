from uuid import uuid4
from sqlalchemy import func, select
from app.db.models_db import Job, Resume, MatchScore
from app.llm.scorer_llm import LLMError
from app.services import scoring_services as scoring


def reqs_html(*items):
    return "<p><strong>Requirements</strong></p><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


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


async def never(requirement, skill):
    return False


async def test_scores_html_requirements_against_resume_skills(session):
    session.add_all([
        Job(title="Backend", description="python and go", content_html=reqs_html("Python", "Go")),
        Resume(user_id=uuid4(), raw_text="python developer"),
    ])
    await session.commit()
    ex = FakeExtractor({"python developer": ["Python"]})

    assert await scoring.score_new(session, ex, FakeEmbedder(), never) == 1

    row = (await session.execute(select(MatchScore))).scalar_one()
    assert row.score == 0.5
    assert row.detail == {"met": ["Python"], "missing": ["Go"], "evidence": {"Python": "Python"}}


async def test_never_scores_or_extracts_twice(session):
    session.add_all([
        Job(title="Python", description="python", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()
    ex, emb = FakeExtractor(), FakeEmbedder()

    await scoring.score_new(session, ex, emb, never)
    calls_after_first = ex.calls
    second = await scoring.score_new(session, ex, emb, never)

    assert second == 0
    assert ex.calls == calls_after_first


async def test_only_shortlisted_jobs_get_requirements_parsed(session):
    session.add_all([
        Job(title="Python Postgres", description="python postgres fastapi", content_html=reqs_html("Python")),
        Job(title="Python", description="python postgres", content_html=reqs_html("Python")),
        Job(title="Python only", description="python", content_html=reqs_html("Python")),
        Job(title="Sales", description="cold calling", content_html=reqs_html("Cold calling")),
        Resume(user_id=uuid4(), raw_text="python postgres fastapi"),
    ])
    await session.commit()

    await scoring.score_new(session, FakeExtractor(), FakeEmbedder(), never, k=2)

    parsed = await session.scalar(select(func.count()).select_from(Job).where(Job.requirements.is_not(None)))
    assert parsed == 2


async def test_failed_resume_extraction_scores_nothing_and_does_not_crash(session):
    session.add_all([
        Job(title="Python", description="python", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()

    assert await scoring.score_new(session, BrokenExtractor(), FakeEmbedder(), never) == 0
    assert (await session.execute(select(MatchScore))).scalars().all() == []
