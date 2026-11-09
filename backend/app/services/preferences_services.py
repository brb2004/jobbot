import re
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, User

Word = Annotated[str, Field(min_length=1, max_length=50)]


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_titles: list[Word] = Field(default=[], max_length=50)   # title must contain one (if set)
    exclude_titles: list[Word] = Field(default=[], max_length=50)   # title must contain none
    locations: list[Word] = Field(default=[], max_length=50)        # a job location must contain one (if set)
    remote_regions: list[Word] = Field(default=[], max_length=50)   # a remote location must also name one (if set)
    years_experience: int | None = Field(default=None, ge=0, le=60)  # jobs asking > this + 1 sink
    extra_skills: list[Word] = Field(default=[], max_length=50)     # skills not on the resume


def has_word(text: str, word: str) -> bool:
    return has_any(text, (word,))


@lru_cache(maxsize=4096)
def _any_word(words: tuple[str, ...]) -> re.Pattern:
    """All words -> ONE compiled pattern, cached. (?<!\\w)/(?!\\w) = whole word; works for 'sr.' where \\b doesn't."""
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alts})(?!\w)", re.IGNORECASE)


def has_any(text: str, words) -> bool:
    return bool(words) and _any_word(tuple(words)).search(text) is not None


def location_ok(location: str | None, prefs: Preferences) -> bool:
    if not prefs.locations:
        return True
    for place in re.split(r"[;|]", location or ""):           # "SF, CA; Remote, US" is two places
        place = place.strip()
        if not place or not has_any(place, prefs.locations):
            continue
        is_remote_elsewhere = (prefs.remote_regions and has_any(place, ("remote",)) and place.lower() != "remote"
                               and not has_any(place, prefs.remote_regions))
        if is_remote_elsewhere:
            continue                                            # e.g. "Remote - Mexico" for a US-only user
        return True
    return False


def allowed(job: Job, prefs: Preferences) -> bool:
    title = job.title or ""
    if has_any(title, prefs.exclude_titles):
        return False
    if prefs.include_titles and not has_any(title, prefs.include_titles):
        return False
    return location_ok(job.location, prefs)


async def get_for(s: AsyncSession, user_id: UUID) -> Preferences | None:
    user = await s.get(User, user_id)
    return Preferences.model_validate(user.preferences or {}) if user else None


async def save_for(s: AsyncSession, user_id: UUID, prefs: Preferences) -> Preferences | None:
    user = await s.get(User, user_id)
    if user is None:
        return None
    user.preferences = prefs.model_dump()
    await s.commit()
    return prefs
