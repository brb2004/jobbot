import re
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
    # (?<!\w) / (?!\w): no letter or digit right before/after. Works for "sr." where \b doesn't.
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE) is not None


def location_ok(location: str | None, prefs: Preferences) -> bool:
    if not prefs.locations:
        return True
    for place in re.split(r"[;|]", location or ""):           # "SF, CA; Remote, US" is two places
        place = place.strip()
        if not place or not any(has_word(place, w) for w in prefs.locations):
            continue
        is_remote_elsewhere = (prefs.remote_regions and has_word(place, "remote") and place.lower() != "remote"
                               and not any(has_word(place, r) for r in prefs.remote_regions))
        if is_remote_elsewhere:
            continue                                            # e.g. "Remote - Mexico" for a US-only user
        return True
    return False


def allowed(job: Job, prefs: Preferences) -> bool:
    title = job.title or ""
    if any(has_word(title, w) for w in prefs.exclude_titles):
        return False
    if prefs.include_titles and not any(has_word(title, w) for w in prefs.include_titles):
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
