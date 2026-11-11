"""Deterministic matching: IDF-weighted skill coverage + inverted index + heap top-k. Same input, same output."""
import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass

PRIOR = 2.0            # imaginary unmet skills (in average-weight units): thin jobs can't hit 100%
YEARS_SLACK = 1        # asking for 1 more year than you have is still worth applying
YEARS_PENALTY = 0.5    # over-asking jobs sink, but stay visible
YEARS_HIDE = 3         # asking for more than you have + 3: not shown at all
# A job that names languages, none of which you have, can't be a strong match (capped below Strong).
LANGUAGES = frozenset({"Python", "Go", "Java", "Ruby", "JavaScript", "TypeScript", "C", "C++", "C#",
                       "Rust", "Kotlin", "Swift", "Scala", "PHP", "Elixir"})
CLEARANCE = re.compile(r"(?<!\w)(?:clearance|u\.?\s?s\.?\s+citizen(?:ship)?|public trust|itar|ts/sci)(?!\w)", re.IGNORECASE)
GOV_TITLE = re.compile(r"(?<!\w)(?:government|federal|public sector)(?!\w)", re.IGNORECASE)
# "5+ years", "3-5 yrs", "2–12+ years": group 1 is the floor of the ask
YEARS = re.compile(r"(?<!\d)(\d{1,2})\s*\+?\s*(?:(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Match:
    job_id: object
    score: float
    matched: list[str]                  # skills you have, heaviest first
    missing: list[str]                  # skills you lack, heaviest first
    years_asked: int | None = None      # what the job asks for, whenever known
    over_years: bool = False            # True = more than you have + slack (score halved)
    no_language: bool = False           # job names languages and you have none (tier capped)


def idf_weights(job_skill_sets: list[set[str]]) -> dict[str, float]:
    """Smoothed IDF: a skill in every job weighs 1.0; rarer skills weigh more."""
    n = len(job_skill_sets)
    df = Counter(s for skills in job_skill_sets for s in skills)
    return {s: math.log((1 + n) / (1 + d)) + 1 for s, d in df.items()}


# When a posting states no number, the title is the next-best evidence. Checked in this order.
TITLE_YEARS = [
    (re.compile(r"(?<!\w)(principal|distinguished)(?!\w)", re.IGNORECASE), 10),
    (re.compile(r"(?<!\w)staff(?!\w)", re.IGNORECASE), 8),
    (re.compile(r"(?<!\w)(senior|sr\.?|lead)(?!\w)", re.IGNORECASE), 5),
    (re.compile(r"(?<!\w)architect(?!\w)", re.IGNORECASE), 5),           # "Solutions Architect", not "architecture"
    # Level numbers, only right after the role word: "Software Engineer II" yes, "Class of 2027" no.
    (re.compile(r"(?<!\w)(?:engineer|developer|swe|sde)\s*[-,]?\s*(?:iv|4)(?!\w)", re.IGNORECASE), 6),
    (re.compile(r"(?<!\w)(?:engineer|developer|swe|sde)\s*[-,]?\s*(?:iii|3)(?!\w)", re.IGNORECASE), 4),
    (re.compile(r"(?<!\w)(?:engineer|developer|swe|sde)\s*[-,]?\s*(?:ii|2)(?!\w)", re.IGNORECASE), 2),
]


def years_from_title(title: str | None) -> int | None:
    return next((n for pattern, n in TITLE_YEARS if pattern.search(title or "")), None)


def years_note(detail: dict) -> str | None:
    """One wording for the email and the page."""
    y = detail.get("years_asked")
    if y is None:
        return None
    if detail.get("years_source") == "title":
        return f"{'senior' if y >= 5 else 'mid'}-level title (~{y}+ years)"
    return f"asks for {y}+ years"


EDUCATION = re.compile(r"\b(?:degree|universit|college|education|graduat|coursework|enrolled|student|school|"
                       r"bachelor|master'?s|ph\.?d|semester)", re.IGNORECASE)


# An ask is about experience when the clause says so, or "N years" leads straight into what was done
# ("5+ years of Python", "3 years in backend", "2 years building APIs"). Not: "a 10 years old codebase".
EXPERIENCE_WORDS = re.compile(r"\b(?:experience|experienced|exp|background|track record)\b", re.IGNORECASE)
YEARS_LEADS_IN = re.compile(r"\s*(?:\)\s*)?(?:of|in|working|building|developing|writing|designing|leading|"
                            r"managing|shipping|programming|coding|professional|industry|hands-on|relevant|"
                            r"related|or\s+more|plus)\b", re.IGNORECASE)


def years_required(bullets: list[str]) -> int | None:
    """Largest 'N+ years' ask. A clause about school ('1 year of university', 'within 1 year of graduation')
    isn't work experience, unless it says 'experience' itself; nor is a number of years that isn't an ask."""
    asks = []
    for b in bullets:
        for clause in re.split(r"[;,]|\.\s", b):
            if EDUCATION.search(clause) and "experience" not in clause.lower():
                continue
            about_work = EXPERIENCE_WORDS.search(clause) is not None \
                or len(re.findall(r"[a-z]{2,}", YEARS.sub("", clause), re.IGNORECASE)) <= 2   # a bare "3-5 years"
            asks += [int(m.group(1)) for m in YEARS.finditer(clause)
                     if about_work or YEARS_LEADS_IN.match(clause, m.end())]
    return max(asks) if asks else None


def score_job(job_id, job_skills: set[str], user_skills: set[str], weights: dict[str, float],
              prior: float = PRIOR, job_years: int | None = None, user_years: int | None = None,
              avg: float | None = None) -> Match | None:
    if not job_skills:
        return None                                          # nothing to judge the job on
    w = lambda s: weights.get(s, 1.0)
    ordered = sorted(job_skills, key=lambda s: (-w(s), s))   # heaviest first, then alphabetical
    matched = [s for s in ordered if s in user_skills]
    missing = [s for s in ordered if s not in user_skills]
    if avg is None:                                          # prior counts in average skills
        avg = sum(weights.values()) / len(weights) if weights else 1.0
    score = sum(map(w, matched)) / (sum(map(w, ordered)) + prior * avg)
    if job_years is not None and user_years is not None and job_years > user_years + YEARS_HIDE:
        return None                                          # far above your level
    over = job_years is not None and user_years is not None and job_years > user_years + YEARS_SLACK
    if over:
        score *= YEARS_PENALTY
    named = job_skills & LANGUAGES
    no_language = bool(named) and not (named & user_skills)
    if no_language:
        score = min(score, LANG_CAP)
    return Match(job_id, round(score, 2), matched, missing, job_years, over, no_language)


def build_index(jobs: dict[object, set[str]]) -> dict[str, set]:
    """Inverted index: skill -> ids of jobs that ask for it."""
    index: dict[str, set] = {}
    for job_id, skills in jobs.items():
        for s in skills:
            index.setdefault(s, set()).add(job_id)
    return index


def top_matches(user_skills: set[str], jobs: dict[object, set[str]], weights: dict[str, float],
                k: int = 20, index: dict[str, set] | None = None,
                job_years: dict[object, int | None] | None = None, user_years: int | None = None,
                allow=None, within: set | None = None, dedupe_key: dict | None = None,
                company: dict | None = None, per_company: int | None = None) -> list[Match]:
    """within: cheap precomputed filter, applied BEFORE scoring. allow: expensive check, applied lazily best-first.
    per_company: at most this many picks from one company (company maps job -> company), so a list
    isn't six postings from two employers."""
    index = index if index is not None else build_index(jobs)
    job_years = job_years or {}
    candidates = set().union(*(index.get(s, set()) for s in user_skills))   # only jobs sharing a skill
    if within is not None:
        candidates &= within                                                # cheap + selective filter first
    avg = sum(weights.values()) / len(weights) if weights else 1.0          # once, not per candidate
    heap = [((-m.score, str(m.job_id)), m) for j in candidates
            if (m := score_job(j, jobs[j], user_skills, weights, job_years=job_years.get(j),
                               user_years=user_years, avg=avg))]
    heapq.heapify(heap)                                                     # O(n)
    out: list[Match] = []
    seen: set = set()                                                       # dedupe keys already used
    taken: dict = {}                                                        # company -> picks so far
    while heap and len(out) < k:
        _, m = heapq.heappop(heap)                                          # O(log n), best first
        key = dedupe_key.get(m.job_id) if dedupe_key else None
        if key is not None and key in seen:
            continue                                                        # a better posting of this role won
        co = company.get(m.job_id) if company and per_company else None
        if co is not None and taken.get(co, 0) >= per_company:
            continue                                                        # this company has its share
        if allow is None or allow(m.job_id):
            out.append(m)
            if key is not None:
                seen.add(key)
            if co is not None:
                taken[co] = taken.get(co, 0) + 1
    return out


# Cutoffs tuned to the matcher's smoothing prior (realistic top ~0.5). Revisit after a few weeks of data.
TIERS = [(0.45, "Strong match"), (0.30, "Worth applying"), (0.0, "Stretch")]


def tier(score: float) -> str:
    return next(label for cut, label in TIERS if score >= cut)

LANG_CAP = round(TIERS[0][0] - 0.01, 2)   # just under Strong


def needs_clearance(title: str | None, bullets: list[str]) -> bool:
    """Flag (never filter): government titles, or requirements asking for clearance or citizenship."""
    return bool(GOV_TITLE.search(title or "")) or any(CLEARANCE.search(b) for b in bullets)
