import re

from pydantic import BaseModel

from app.db.models_db import Job


class Preferences(BaseModel):
    exclude_titles: list[str] = []          # whole words, case-insensitive: "intern", "senior", "sr."


def allowed(job: Job, prefs: Preferences) -> bool:
    title = job.title or ""
    for word in prefs.exclude_titles:
        # (?<!\w) / (?!\w): no letter or digit right before/after. Works for "sr." where \b doesn't.
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", title, re.IGNORECASE):
            return False
    return True
