import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, User

Word = Annotated[str, Field(min_length=1, max_length=50)]


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")                       # unknown fields -> 422
    include_titles: list[Word] = Field(default=[], max_length=50)  # title must contain one (if set)
    exclude_titles: list[Word] = Field(default=[], max_length=50)  # title must contain none


def has_word(title: str, word: str) -> bool:
    # (?<!\w) / (?!\w): no letter or digit right before/after. Works for "sr." where \b doesn't.
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", title, re.IGNORECASE) is not None


def allowed(job: Job, prefs: Preferences) -> bool:
    title = job.title or ""
    if any(has_word(title, w) for w in prefs.exclude_titles):
        return False
    if prefs.include_titles and not any(has_word(title, w) for w in prefs.include_titles):
        return False
    return True


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
