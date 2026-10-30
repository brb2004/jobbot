from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, Resume, TermVector
from app.llm.scorer_llm import normalize

BATCH = 64


async def all_terms(s: AsyncSession) -> set[str]:
    reqs = (await s.execute(select(Job.requirements).where(Job.requirements.is_not(None)))).scalars().all()
    skills = (await s.execute(select(Resume.skills).where(Resume.skills.is_not(None)))).scalars().all()
    return {normalize(t) for group in [*reqs, *skills] for t in group if normalize(t)}


async def embed_new_terms(s: AsyncSession, embedder, terms: set[str] | None = None) -> int:
    """Embed every term that has no vector yet. Pass `terms` to limit it to just those."""
    wanted = {normalize(t) for t in terms if normalize(t)} if terms is not None else await all_terms(s)
    known = set((await s.execute(select(TermVector.term))).scalars().all())
    new = sorted(wanted - known)
    for i in range(0, len(new), BATCH):
        batch = new[i:i + BATCH]
        for term, vector in zip(batch, await embedder.embed(batch)):
            s.add(TermVector(term=term, vector=vector))
        await s.commit()
    return len(new)


async def vectors_for(s: AsyncSession, terms: list[str]) -> dict[str, list[float]]:
    keys = {normalize(t) for t in terms}
    rows = (await s.execute(select(TermVector).where(TermVector.term.in_(keys)))).scalars().all()
    return {r.term: list(r.vector) for r in rows}
