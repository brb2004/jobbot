import heapq
import math
from collections import Counter
from dataclasses import dataclass, field

PRIOR = 2.0  # imaginary unmet skills, in average-weight units, so a thin posting can't score 100%
YEARS_SLACK = 1  # one year more than you have is still worth applying for
YEARS_PENALTY = 0.5
YEARS_HIDE = 3  # more than you have + 3: not shown at all
TIERS = [(0.45, "Strong match"), (0.30, "Worth applying"), (0.0, "Stretch")]  # realistic top is ~0.5
LANG_CAP = round(TIERS[0][0] - 0.01, 2)  # names languages you have none of: never "Strong"
LANGUAGES = frozenset(
    "Python Go Java Ruby JavaScript TypeScript C C++ C# Rust Kotlin Swift Scala PHP Elixir".split()
)


@dataclass(frozen=True)
class Match:
    job_id: object
    score: float
    matched: list[str]  # heaviest first
    missing: list[str]
    years_asked: int | None = None
    over_years: bool = False
    no_language: bool = False


def idf_weights(job_skill_sets: list[set[str]]) -> dict[str, float]:
    n = len(job_skill_sets)
    df = Counter(s for skills in job_skill_sets for s in skills)
    return {s: math.log((1 + n) / (1 + d)) + 1 for s, d in df.items()}


def score_job(
    job_id, job_skills, user_skills, weights, prior=PRIOR, job_years=None, user_years=None, avg=None
):
    if not job_skills:
        return None
    if job_years is not None and user_years is not None and job_years > user_years + YEARS_HIDE:
        return None
    ordered = sorted(job_skills, key=lambda s: (-weights.get(s, 1.0), s))
    matched = [s for s in ordered if s in user_skills]
    avg = avg if avg is not None else _average(weights)
    score = sum(weights.get(s, 1.0) for s in matched) / (
        sum(weights.get(s, 1.0) for s in ordered) + prior * avg
    )
    over = job_years is not None and user_years is not None and job_years > user_years + YEARS_SLACK
    named = job_skills & LANGUAGES
    no_language = bool(named) and not (named & user_skills)
    score = min(score * (YEARS_PENALTY if over else 1), LANG_CAP if no_language else 1)
    missing = [s for s in ordered if s not in user_skills]
    return Match(job_id, round(score, 2), matched, missing, job_years, over, no_language)


def _average(weights: dict[str, float]) -> float:
    return sum(weights.values()) / len(weights) if weights else 1.0


def build_index(jobs: dict[object, set[str]]) -> dict[str, set]:
    index: dict[str, set] = {}
    for job_id, skills in jobs.items():
        for s in skills:
            index.setdefault(s, set()).add(job_id)
    return index


@dataclass
class _Picker:
    k: int
    dedupe_key: dict | None
    company: dict | None
    per_company: int | None
    allow: object = None
    out: list = field(default_factory=list)
    seen: set = field(default_factory=set)
    taken: Counter = field(default_factory=Counter)

    def offer(self, m: Match) -> None:
        key = self.dedupe_key.get(m.job_id) if self.dedupe_key else None
        co = self.company.get(m.job_id) if self.company and self.per_company else None
        if (key is not None and key in self.seen) or (co is not None and self.taken[co] >= self.per_company):
            return
        if self.allow is None or self.allow(m.job_id):
            self.out.append(m)
            self.seen.add(key)
            self.taken[co] += 1


def top_matches(
    user_skills,
    jobs,
    weights,
    k=20,
    index=None,
    job_years=None,
    user_years=None,
    allow=None,
    within=None,
    dedupe_key=None,
    company=None,
    per_company=None,
) -> list[Match]:
    index = index if index is not None else build_index(jobs)
    job_years, avg = job_years or {}, _average(weights)
    candidates = set().union(*(index.get(s, set()) for s in user_skills))
    if within is not None:
        candidates &= within
    scored = (
        score_job(j, jobs[j], user_skills, weights, PRIOR, job_years.get(j), user_years, avg)
        for j in candidates
    )
    heap = [((-m.score, str(m.job_id)), m) for m in scored if m]
    heapq.heapify(heap)
    picker = _Picker(k, dedupe_key, company, per_company, allow)
    while heap and len(picker.out) < k:
        picker.offer(heapq.heappop(heap)[1])
    return picker.out


def tier(score: float) -> str:
    return next(label for cut, label in TIERS if score >= cut)
