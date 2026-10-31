from uuid import uuid4
from sqlalchemy import select
from app.db.models_db import Job, Resume, MatchScore
from app.llm.scorer_llm import LLMError
from app.services import scoring_services as scoring


def reqs_html(*items):
    return "<p><strong>Requirements</strong></p><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


class FakeExtractor:
    def __init__(self, mapping=None, default=("Python",)):
        self.mapping, self.default, self.calls = mapping or {}, list(default), 0

    async def extract(self, text):
        self.calls += 1
        return self.mapping.get(text, self.default)


class BrokenExtractor:
    async def extract(self, text):
        raise LLMError("nonsense")


class FakeFit:
    """Met if the requirement is literally one of the skills."""
    def __init__(self):
        self.calls = 0

    async def __call__(self, requirement, skills):
        self.calls += 1
        return 1.0 if requirement.lower() in {s.lower() for s in skills} else 0.0


class BrokenFit:
    async def __call__(self, requirement, skills):
        raise LLMError("nonsense")


async def test_scores_each_requirement_against_the_resume(session):
    session.add_all([
        Job(title="Backend", description="python and go", content_html=reqs_html("Python", "Go")),
        Resume(user_id=uuid4(), raw_text="python developer"),
    ])
    await session.commit()

    assert await scoring.score_new(session, FakeExtractor({"python developer": ["Python"]}), FakeFit()) == 1

    row = (await session.execute(select(MatchScore))).scalar_one()
    assert row.score == 0.5
    assert row.detail == {"met": ["Python"], "partial": [], "missing": ["Go"], "soft": []}


async def test_jobs_without_requirements_never_take_a_shortlist_slot(session):
    session.add_all([
        Job(title="Python Engineer"),
        Job(title="Backend", description="python services", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python engineer"),
    ])
    await session.commit()

    assert await scoring.score_new(session, FakeExtractor(), FakeFit(), k=1) == 1


async def test_never_scores_or_extracts_twice(session):
    session.add_all([
        Job(title="Python", description="python", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()
    ex, fit = FakeExtractor(), FakeFit()

    await scoring.score_new(session, ex, fit)
    before = (ex.calls, fit.calls)
    second = await scoring.score_new(session, ex, fit)

    assert second == 0
    assert (ex.calls, fit.calls) == before


async def test_only_top_k_jobs_get_scored(session):
    session.add_all([
        Job(title="Python Postgres", description="python postgres fastapi", content_html=reqs_html("Python")),
        Job(title="Python", description="python postgres", content_html=reqs_html("Python")),
        Job(title="Python only", description="python", content_html=reqs_html("Python")),
        Job(title="Sales", description="cold calling", content_html=reqs_html("Cold calling")),
        Resume(user_id=uuid4(), raw_text="python postgres fastapi"),
    ])
    await session.commit()

    assert await scoring.score_new(session, FakeExtractor(), FakeFit(), k=2) == 2


async def test_failed_resume_extraction_scores_nothing(session):
    session.add_all([
        Job(title="Python", description="python", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()

    assert await scoring.score_new(session, BrokenExtractor(), FakeFit()) == 0


async def test_failed_fit_judgment_skips_the_pair_and_retries_later(session):
    session.add_all([
        Job(title="Python", description="python", content_html=reqs_html("Python")),
        Resume(user_id=uuid4(), raw_text="python"),
    ])
    await session.commit()

    assert await scoring.score_new(session, FakeExtractor(), BrokenFit()) == 0
    assert await scoring.score_new(session, FakeExtractor(), FakeFit()) == 1
