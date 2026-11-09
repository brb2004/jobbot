"""Deterministic matching: IDF-weighted skill coverage + inverted index + heap top-k. Same input, same output."""
import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass

PRIOR = 2.0            # imaginary unmet skills (in average-weight units): thin jobs can't hit 100%
YEARS_SLACK = 1        # asking for 1 more year than you have is still worth applying
YEARS_PENALTY = 0.5    # over-asking jobs sink, but stay visible
# "5+ years", "3-5 yrs", "2–12+ years": group 1 is the floor of the ask
YEARS = re.compile(r"(?<!\d)(\d{1,2})\s*\+?\s*(?:(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Match:
    job_id: object
    score: float
    matched: list[str]                  # skills you have, heaviest first
    missing: list[str]                  # skills you lack, heaviest first
    years_asked: int | None = None      # set only when the job asks for more than you have


def idf_weights(job_skill_sets: list[set[str]]) -> dict[str, float]:
    """Smoothed IDF: a skill in every job weighs 1.0; rarer skills weigh more."""
    n = len(job_skill_sets)
    df = Counter(s for skills in job_skill_sets for s in skills)
    return {s: math.log((1 + n) / (1 + d)) + 1 for s, d in df.items()}


def years_required(bullets: list[str]) -> int | None:
    asks = [int(m.group(1)) for b in bullets for m in YEARS.finditer(b)]
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
    flag = None
    if job_years is not None and user_years is not None and job_years > user_years + YEARS_SLACK:
        score *= YEARS_PENALTY
        flag = job_years
    return Match(job_id, round(score, 2), matched, missing, flag)


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
                allow=None, within: set | None = None) -> list[Match]:
    """within: cheap precomputed filter, applied BEFORE scoring. allow: expensive check, applied lazily best-first."""
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
    while heap and len(out) < k:
        _, m = heapq.heappop(heap)                                          # O(log n), best first
        if allow is None or allow(m.job_id):
            out.append(m)
    return out
