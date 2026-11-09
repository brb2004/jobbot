import re
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, User

Word = Annotated[str, Field(min_length=1, max_length=50)]
# Tech-only product: with no include list, show engineering roles. Users can override with their own list.
DEFAULT_TITLES = ("engineer", "developer", "sre", "devops", "architect", "programmer", "scientist")


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_titles: list[Word] = Field(default=[], max_length=50)   # title must contain one (empty = DEFAULT_TITLES)
    exclude_titles: list[Word] = Field(default=[], max_length=50)   # title must contain none
    locations: list[Word] = Field(default=[], max_length=50)        # a job location must contain one (if set)
    remote_regions: list[Word] = Field(default=[], max_length=50)   # a remote location must also name one (if set)
    years_experience: int | None = Field(default=None, ge=0, le=60)  # jobs asking > this + 1 sink
    extra_skills: list[Word] = Field(default=[], max_length=50)     # skills not on the resume


def has_word(text: str, word: str) -> bool:
    return has_any(text, (word,))


@lru_cache(maxsize=4096)
def _any_word(words: tuple[str, ...], hyphen_joins: bool) -> re.Pattern:
    """All words -> ONE compiled pattern, cached. hyphen_joins: 'go' must not match inside 'Go-to-Market'."""
    edge = r"[\w-]" if hyphen_joins else r"\w"
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!{edge})(?:{alts})(?!{edge})", re.IGNORECASE)


def has_any(text: str, words, hyphen_joins: bool = False) -> bool:
    return bool(words) and _any_word(tuple(words), hyphen_joins).search(text) is not None


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
    if has_any(title, prefs.exclude_titles, hyphen_joins=True):
        return False
    if not has_any(title, prefs.include_titles or DEFAULT_TITLES, hyphen_joins=True):
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
    from app.services.matching_services import match_all   # local import: matching imports this module
    await match_all(s, user_id=user_id)                     # new filters show up now, not at the next cron run
    return prefs
