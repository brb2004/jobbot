import re

from app.db.models_db import Job

WORD = re.compile(r"[a-z][a-z0-9+#.]*")          # keeps c++, c#, node.js
STOP = {"and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "at", "is", "are", "we", "you"}


def terms(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 1 and w not in STOP}


def top_k(resume_text: str, jobs: list[Job], k: int = 20) -> list[Job]:
    mine = terms(resume_text)
    scored = []
    for j in jobs:
        theirs = terms(f"{j.title} {j.description or ''}")
        shared = len(mine & theirs)
        if shared:
            scored.append((shared / len(theirs), j))     # fraction, not count
    scored.sort(key=lambda x: x[0], reverse=True)
    return [j for _, j in scored[:k]]