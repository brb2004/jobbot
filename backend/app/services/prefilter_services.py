import re

from app.db.models_db import Job

WORD = re.compile(r"[a-z][a-z0-9+#.]*")          # keeps c++, c#, node.js
STOP = {"and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "at", "is", "are", "we", "you"}


def terms(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 1 and w not in STOP}


def top_k(resume_text: str, jobs: list[Job], k: int = 20) -> list[Job]:
    mine = terms(resume_text)
    scored = [(len(mine & terms(f"{j.title} {j.description or ''}")), j) for j in jobs]
    scored = [(n, j) for n, j in scored if n > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [j for _, j in scored[:k]]