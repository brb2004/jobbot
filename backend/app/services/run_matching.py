import asyncio
import sys

from app.core.db_core import SessionLocal, engine
from app.services.extraction_services import fill_job_requirements
from app.services.matching_services import match_all, tag_jobs, tag_resumes


async def main(k: int) -> None:
    async with SessionLocal() as s:
        reqs = await fill_job_requirements(s)
        jobs = await tag_jobs(s)
        resumes = await tag_resumes(s)
        saved = await match_all(s, k)
    await engine.dispose()
    print(
        f"requirements filled: {reqs}  jobs tagged: {jobs}  resumes tagged: {resumes}  matches saved: {saved}"
    )


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
