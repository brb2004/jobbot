from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, Resume
from app.llm.scorer_llm import LLMError, unique

CHUNK_CHARS = 800          # small enough that a 7B model reads every line


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Group whole lines into pieces of at most `size` characters (a single longer line stands alone)."""
    out, cur = [], ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if cur and len(cur) + 1 + len(line) > size:
            out.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


async def extract_all(extractor, text: str, chunk_size: int = CHUNK_CHARS) -> list[str]:
    parts = chunks(text, chunk_size)
    if len(parts) > 1:
        parts = [text, *parts]                  # whole-text pass + chunk passes: each misses different things
    found: list[str] = []
    for part in parts:
        found += await extractor.extract(part)
    return unique(found)

async def extract_job_requirements(s: AsyncSession, extractor, job_ids=None, chunk_size: int = CHUNK_CHARS) -> int:
    stmt = select(Job).where(Job.requirements.is_(None), Job.description.is_not(None))
    if job_ids is not None:
        if not job_ids:
            return 0
        stmt = stmt.where(Job.id.in_(job_ids))
    jobs = (await s.execute(stmt)).scalars().all()

    done = 0
    for job in jobs:
        try:
            job.requirements = await extract_all(extractor, job.description, chunk_size)
        except LLMError:
            continue
        await s.commit()
        done += 1
    return done


async def extract_resume_skills(s: AsyncSession, extractor, chunk_size: int = CHUNK_CHARS,
                                background=None) -> int:
    """Skills (chunked) and, if a background extractor is given, education + experience. Each once, cached."""
    todo = Resume.skills.is_(None)
    if background is not None:
        todo = or_(todo, Resume.education.is_(None))
    stmt = select(Resume).where(todo, Resume.raw_text.is_not(None))
    resumes = (await s.execute(stmt)).scalars().all()

    done = 0
    for resume in resumes:
        try:
            if resume.skills is None:
                resume.skills = await extract_all(extractor, resume.raw_text, chunk_size)
            if background is not None and resume.education is None:
                found = await background.extract_background(resume.raw_text)
                resume.education, resume.experience = found["education"], found["experience"]
        except LLMError:
            continue
        await s.commit()
        done += 1
    return done


async def fill_job_requirements(s: AsyncSession, job_ids=None) -> int:
    """Requirements straight from the posting's HTML requirements section. No AI."""
    from app.ingest.sections_ingest import requirement_bullets

    stmt = select(Job).where(Job.requirements.is_(None), Job.content_html.is_not(None))
    if job_ids is not None:
        if not job_ids:
            return 0
        stmt = stmt.where(Job.id.in_(job_ids))
    jobs = (await s.execute(stmt)).scalars().all()
    for job in jobs:
        job.requirements = requirement_bullets(job.content_html)     # [] when there's no section
    await s.commit()
    return len(jobs)
