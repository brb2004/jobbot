"""Which tech terms do postings ask for that skills.txt doesn't know? A read-only report for a person to review.

    python -m app.services.skill_gaps [top_n] [min_companies]

Known skills are blanked out first (so "GitHub Actions" doesn't leave "Actions" behind), then what's left is
scanned for words that look technical: inner capitals (SQLAlchemy, gRPC), digits or symbols (Node.js, C#, x86),
short acronyms (JWT, SIEM), and capitalised words mid-sentence (Kafka, Snowflake), plus pairs of those
("Spring Boot"). Ranked by how many COMPANIES ask: one company repeating its own product name can't win."""
import asyncio
import re
import sys
from collections import defaultdict

from sqlalchemy import select

TOKEN = re.compile(r"[A-Za-z.][A-Za-z0-9.#+/-]*[A-Za-z0-9#+]|[A-Za-z]")
# Capitalised words that aren't skills. Short on purpose: the company count and a human do the rest.
STOP = {w.lower() for w in """
    a an and or the of in on to for with as at by from our we you your their this that these those is are be will
    must should can may plus preferred required nice bonus including such etc e.g i.e eg ie ability able strong
    excellent good great solid proven deep hands-on experience experienced knowledge understanding familiarity
    proficiency proficient working work skills skill background bachelor bachelors master masters phd ms bs ba
    degree computer science engineering engineer engineers software data cloud platform product products team
    teams customer customers business year years minimum least equivalent related field similar other tools
    technologies technology systems system services service development developer developers design senior
    junior lead staff principal manager us usa u.s united states america american english spanish french remote
    hybrid office time full part new high low level levels based first one two three four five six ten more
    must-have nice-to-have opportunity role position company apply equal employer comfortable demonstrated
    track record communication written verbal collaborative collaboration environment environments fast-paced
    startup startups who what why how when where all any each both i it its it's they them he she his her
    january february march april may june july august september october november december monday friday
    """.split()}


def _techy(tok: str, first: bool) -> bool:
    if tok.lower() in STOP or len(tok) < 2 and tok not in {"R"}:
        return False
    if "/" in tok and all(part.lower() in STOP for part in tok.split("/") if part):
        return False                                       # "and/or", "his/her"
    return (any(c.isupper() for c in tok[1:])            # SQLAlchemy, gRPC, iOS, JWT
            or any(c.isdigit() or c in ".#+/" for c in tok)   # Node.js, C#, x86, S3
            or (tok[0].isupper() and not first))           # Kafka mid-sentence (not "Strong ..." at the start)


def candidates(text: str, tagger) -> set[str]:
    """Technical-looking terms in one bullet that the tagger doesn't already know."""
    rest = tagger.pattern.sub(" | ", text or "")             # known skills out; '|' stops pairs forming across them
    found, prev = set(), None
    for i, m in enumerate(TOKEN.finditer(rest)):
        tok = m.group().strip(".-/")
        first = i == 0 or rest[max(0, m.start() - 2):m.start()].strip() in {".", ":", "-", "•", "|", "("}
        single = bool(tok) and _techy(tok, first) and not tagger.tag(tok)
        cap = bool(tok) and tok[0].isupper()
        if single:
            found.add(tok)
        if prev and cap and (prev[2] or single) and not rest[prev[1]:m.start()].strip():
            pair = f"{prev[0]} {tok}"                        # "Spring Boot", "Google Cloud" ("Cloud" alone is too vague)
            if not tagger.tag(pair):
                found.add(pair)
        prev = (tok, m.end(), single) if (single or cap) and not first else None
    return found


class Tally:
    """Counts as postings stream past, so the whole table never sits in memory. Each term once per posting."""
    def __init__(self, tagger):
        self.tagger, self.postings_seen = tagger, 0
        self.companies, self.postings, self.example = defaultdict(set), defaultdict(int), {}

    def add(self, company: str, bullets: list[str] | None) -> None:
        self.postings_seen += 1
        seen = set()
        for b in bullets or []:
            for term in candidates(b, self.tagger):
                if term not in seen:
                    seen.add(term)
                    self.example.setdefault(term, b[:200])
        for term in seen:
            self.companies[term].add(company)
            self.postings[term] += 1

    def ranked(self, min_companies: int = 3) -> list[tuple[str, int, int, str]]:
        """[(term, companies, postings, example)], most companies first."""
        out = [(t, len(c), self.postings[t], self.example[t]) for t, c in self.companies.items()
               if len(c) >= min_companies]
        return sorted(out, key=lambda r: (-r[1], -r[2], r[0].lower()))


def rank(rows, tagger, min_companies: int = 3):
    tally = Tally(tagger)
    for company, bullets in rows:
        tally.add(company, bullets)
    return tally.ranked(min_companies)


async def main(top_n: int, min_companies: int) -> None:
    from app.core.db_core import SessionLocal, engine
    from app.db.models_db import Job
    from app.services.preferences_services import Preferences, allowed
    from app.services.skills_services import default_tagger

    everyone = Preferences()                                # the matcher's default title rules: engineering roles
    tally = Tally(default_tagger())
    async with SessionLocal() as s:
        stream = await s.stream(select(Job.board, Job.title, Job.location, Job.requirements)
                                .where(Job.closed_at.is_(None), Job.requirements.is_not(None))
                                .execution_options(yield_per=2000))            # streamed: flat memory
        async for board, title, location, reqs in stream:
            if allowed(Job(title=title, location=location), everyone):   # only jobs the matcher would show
                tally.add(board, reqs)
    await engine.dispose()
    ranked = tally.ranked(min_companies)
    print(f"{tally.postings_seen} open ENGINEERING postings with requirements; {len(ranked)} unknown terms asked by "
          f">= {min_companies} companies. Top {top_n}:\n")
    print(f"{'term':<28}{'companies':>10}{'postings':>10}  example")
    for term, n_co, n_post, ex in ranked[:top_n]:
        ex = re.sub(r"\s+", " ", ex).strip()
        print(f"{term[:27]:<28}{n_co:>10}{n_post:>10}  {ex[:90]}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 150,
                     int(sys.argv[2]) if len(sys.argv) > 2 else 3))
