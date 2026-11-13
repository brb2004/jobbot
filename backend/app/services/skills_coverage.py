"""Dev tool: how much of the real job data does skills.txt understand, and what is it missing?
Run: python -m app.services.skills_coverage"""

import asyncio
import re
from collections import Counter

from sqlalchemy import select

from app.core.db_core import SessionLocal, engine
from app.db.models_db import Job
from app.services.extraction_services import fill_job_requirements
from app.services.skills_services import default_tagger

# a run of capitalized / symbol-y words: "Apache Flink", "Next.js", "C/C++", "SOC2"
NAME = re.compile(r"(?<![\w.])(?:[A-Z][\w.+#/-]*|[a-z]+[A-Z][\w]*)(?:\s+(?:[A-Z][\w.+#/-]*))*")
ENGINEERING = re.compile(r"engineer|developer|\bsre\b|devops|scientist|architect", re.I)
STOP = set(
    [
        "a",
        "an",
        "and",
        "or",
        "the",
        "of",
        "in",
        "on",
        "for",
        "with",
        "to",
        "at",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "you",
        "we",
        "our",
        "your",
        "their",
        "this",
        "that",
        "it",
        "its",
        "experience",
        "experienced",
        "strong",
        "ability",
        "able",
        "bachelor",
        "bachelor's",
        "bachelors",
        "master",
        "master's",
        "masters",
        "phd",
        "degree",
        "science",
        "computer",
        "engineering",
        "engineer",
        "engineers",
        "software",
        "years",
        "year",
        "knowledge",
        "familiarity",
        "familiar",
        "excellent",
        "proven",
        "demonstrated",
        "understanding",
        "proficiency",
        "proficient",
        "working",
        "track",
        "record",
        "team",
        "teams",
        "plus",
        "bonus",
        "preferred",
        "required",
        "including",
        "e.g",
        "i.e",
        "etc",
        "such",
        "other",
        "related",
        "field",
        "equivalent",
        "practical",
        "minimum",
        "least",
        "deep",
        "good",
        "solid",
        "hands-on",
        "high",
        "skills",
        "skill",
        "background",
        "expertise",
        "comfort",
        "comfortable",
        "passion",
        "interest",
        "desire",
        "us",
        "u.s",
        "english",
        "must",
        "nice",
        "ideally",
        "previous",
        "prior",
        "professional",
        "industry",
        "production",
        "systems",
        "system",
        "technical",
        "tools",
        "design",
    ]
)


def unknown_names(bullet: str, tagger) -> set[str]:
    text = tagger.pattern.sub(" ", bullet)  # erase skills we already know
    found = set()
    for m in NAME.finditer(text):
        if m.start() == 0 or text[: m.start()].rstrip().endswith((".", ":", ";")):
            continue  # sentence start: capitalized for grammar
        words = [w for w in m.group().split() if w.lower().strip(".,") not in STOP]
        if words and len(" ".join(words)) > 1:
            found.add(" ".join(words).strip(".,"))
    return found


async def main() -> None:
    tagger = default_tagger()
    async with SessionLocal() as s:
        await fill_job_requirements(s)
        jobs = (await s.scalars(select(Job).where(Job.requirements.is_not(None)))).all()
    await engine.dispose()

    jobs = [j for j in jobs if j.requirements and ENGINEERING.search(j.title or "")]
    bullets = [b for j in jobs for b in j.requirements]
    tagged = sum(1 for b in bullets if tagger.tag(b))
    known, unknown = Counter(), Counter()
    jobs_with_skill = 0
    for j in jobs:
        skills = set().union(*(tagger.tag(b) for b in j.requirements))
        jobs_with_skill += bool(skills)
        known.update(skills)
        unknown.update(set().union(*(unknown_names(b, tagger) for b in j.requirements)))

    print(f"jobs with requirements : {len(jobs)}")
    print(f"jobs with >=1 skill    : {jobs_with_skill} ({jobs_with_skill / len(jobs):.0%})")
    print(f"bullets with >=1 skill : {tagged}/{len(bullets)} ({tagged / len(bullets):.0%})\n")
    print("top known skills (jobs):")
    for name, n in known.most_common(20):
        print(f"  {n:5}  {name}")
    print("\ntop UNKNOWN names (jobs) -> candidates for skills.txt:")
    for name, n in unknown.most_common(80):
        print(f"  {n:5}  {name}")


if __name__ == "__main__":
    asyncio.run(main())
