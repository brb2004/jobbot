from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import TermMatch
from app.llm.scorer_llm import LLMError, normalize


class CachedJudge:
    """Wraps any judge. Each (requirement, skill) pair is decided once, then read from the database forever."""

    def __init__(self, s: AsyncSession, judge):
        self.s = s
        self.judge = judge

    async def __call__(self, requirement: str, skill: str) -> bool:
        key = (normalize(requirement), normalize(skill))
        cached = await self.s.get(TermMatch, key)
        if cached is not None:
            return cached.verdict
        try:
            verdict = await self.judge(requirement, skill)
        except LLMError:
            return False                    # not cached: asked again next run
        self.s.add(TermMatch(requirement=key[0], skill=key[1], verdict=verdict))
        await self.s.flush()
        return verdict
