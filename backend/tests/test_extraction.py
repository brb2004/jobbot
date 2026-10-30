from sqlalchemy import select

from app.db.models_db import Job
from app.llm.scorer_llm import LLMError
from app.services import extraction_services as extraction


class FakeExtractor:
    def __init__(self, result=None):
        self.result = result or ["Python", "Docker"]
        self.calls = 0

    async def extract(self, text: str) -> list[str]:
        self.calls += 1
        return self.result


class BrokenExtractor:
    async def extract(self, text):
        raise LLMError("nonsense")


async def test_job_requirements_are_extracted_once_and_cached(session):
    session.add_all([
        Job(title="A", description="python docker"),                  # needs extraction
        Job(title="B", description="go", requirements=["Go"]),        # already cached
        Job(title="C"),                                               # no description, nothing to read
    ])
    await session.commit()
    ex = FakeExtractor()

    first = await extraction.extract_job_requirements(session, ex)
    second = await extraction.extract_job_requirements(session, ex)

    assert (first, second) == (1, 0)
    assert ex.calls == 1
    job = (await session.execute(select(Job).where(Job.title == "A"))).scalar_one()
    assert job.requirements == ["Python", "Docker"]


async def test_failed_extraction_is_retried_next_run(session):
    session.add(Job(title="A", description="python"))
    await session.commit()

    assert await extraction.extract_job_requirements(session, BrokenExtractor()) == 0
    assert await extraction.extract_job_requirements(session, FakeExtractor()) == 1
from uuid import uuid4
from app.db.models_db import Resume


async def test_resume_skills_are_extracted_once_and_cached(session):
    session.add_all([
        Resume(user_id=uuid4(), raw_text="python docker"),                   # needs extraction
        Resume(user_id=uuid4(), raw_text="go", skills=["Go"]),               # already cached
    ])
    await session.commit()
    ex = FakeExtractor()

    first = await extraction.extract_resume_skills(session, ex)
    second = await extraction.extract_resume_skills(session, ex)

    assert (first, second) == (1, 0)
    assert ex.calls == 1