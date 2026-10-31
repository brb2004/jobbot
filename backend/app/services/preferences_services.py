import re

from pydantic import BaseModel

from app.db.models_db import Job


class Preferences(BaseModel):
    include_titles: list[str] = []          # if set, the title must contain at least one of these words
    exclude_titles: list[str] = []          # the title must contain none of these words


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
