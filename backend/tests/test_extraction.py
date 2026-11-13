from app.db.models_db import Job
from app.services import extraction_services as extraction


async def test_job_requirements_come_from_the_html_requirements_section(session):
    with_section = Job(
        title="A", content_html="<p><strong>Requirements</strong></p><ul><li>Go</li><li>SQL</li></ul>"
    )
    without = Job(title="B", content_html="<p>No sections here</p>")
    session.add_all([with_section, without])
    await session.commit()

    assert await extraction.fill_job_requirements(session) == 2
    assert with_section.requirements == ["Go", "SQL"]
    assert without.requirements == []
    assert await extraction.fill_job_requirements(session) == 0
