"""Deterministic matching: IDF-weighted skill coverage + inverted index + heap top-k. Same input, same output."""
import heapq
import math
from collections import Counter
from dataclasses import dataclass


PRIOR = 2.0     # imaginary unmet weight: a job naming 1 skill can't outrank one naming 6


@dataclass(frozen=True)
class Match:
    job_id: object
    score: float
    matched: list[str]      # skills you have, heaviest first
    missing: list[str]      # skills you lack, heaviest first


def idf_weights(job_skill_sets: list[set[str]]) -> dict[str, float]:
    """Smoothed IDF: a skill in every job weighs 1.0; rarer skills weigh more."""
    n = len(job_skill_sets)
    df = Counter(s for skills in job_skill_sets for s in skills)
    return {s: math.log((1 + n) / (1 + d)) + 1 for s, d in df.items()}


def score_job(job_id, job_skills: set[str], user_skills: set[str], weights: dict[str, float],
              prior: float = PRIOR) -> Match | None:
    if not job_skills:
        return None                                          # nothing to judge the job on
    w = lambda s: weights.get(s, 1.0)
    ordered = sorted(job_skills, key=lambda s: (-w(s), s))   # heaviest first, then alphabetical
    matched = [s for s in ordered if s in user_skills]
    missing = [s for s in ordered if s not in user_skills]
    score = sum(map(w, matched)) / (sum(map(w, ordered)) + prior)
    return Match(job_id, round(score, 2), matched, missing)


def build_index(jobs: dict[object, set[str]]) -> dict[str, set]:
    """Inverted index: skill -> ids of jobs that ask for it."""
    index: dict[str, set] = {}
    for job_id, skills in jobs.items():
        for s in skills:
            index.setdefault(s, set()).add(job_id)
    return index


def top_matches(user_skills: set[str], jobs: dict[object, set[str]], weights: dict[str, float],
                k: int = 20, index: dict[str, set] | None = None) -> list[Match]:
    index = index if index is not None else build_index(jobs)
    candidates = set().union(*(index.get(s, set()) for s in user_skills))   # only jobs sharing a skill
    results = [m for j in candidates if (m := score_job(j, jobs[j], user_skills, weights))]
    return heapq.nsmallest(k, results, key=lambda m: (-m.score, str(m.job_id)))   # O(n log k)
