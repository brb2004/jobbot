"""Debug tool: score one job against your resume and explain every met-claim. Not used in production."""
import asyncio
import json
import re
import sys
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select

from app.core.config_core import get_settings
from app.core.db_core import SessionLocal, engine
from app.db.models_db import Job, Resume
from app.llm import scorer_llm as sl


async def main(job_id: str) -> None:
    cfg = get_settings()
    async with SessionLocal() as s:
        job = await s.get(Job, UUID(job_id))
        resume = (await s.execute(select(Resume).limit(1))).scalar_one()
    await engine.dispose()

    resume_text = (resume.raw_text or "")[:sl.MAX_CHARS]
    client = AsyncOpenAI(base_url=cfg.LLM_API_URL, api_key=cfg.LLM_API_KEY, timeout=300)
    resp = await client.chat.completions.create(
        model=cfg.LLM_MODEL, temperature=0,
        messages=[{"role": "user", "content": sl.PROMPT.format(
            resume=resume_text, title=job.title or "", description=(job.description or "")[:sl.MAX_CHARS])}],
    )
    raw = resp.choices[0].message.content or ""
    print("=== RAW MODEL OUTPUT ===\n", raw, "\n")

    data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    resume_words = set(sl.normalize(resume_text).split())
    print("=== MET CLAIMS ===")
    for item in data.get("met", []):
        req, ev = str(item.get("requirement", "")), str(item.get("evidence", ""))
        not_in_resume = sl.keywords(ev) - resume_words
        problems = []
        if not_in_resume:
            problems.append(f"words not in resume: {sorted(not_in_resume)}")
        if len(sl.normalize(ev).split()) > sl.MAX_QUOTE_WORDS:
            problems.append("quote too long")
        if not (sl.keywords(req) & sl.keywords(ev)):
            problems.append("no shared keyword with requirement")
        print(("KEEP " if not problems else "DROP ") + req[:70])
        print(f"     quote: {ev[:90]!r}")
        for p in problems:
            print(f"     -> {p}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))