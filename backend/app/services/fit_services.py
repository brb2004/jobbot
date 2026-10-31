import re

from app.llm.scorer_llm import ScoreResult, unique

SMOOTHING = 2      # imaginary unmet requirements: thin evidence pulls the score toward 0
REQUIRED = re.compile(r"\(required\)", re.IGNORECASE)        # explicit dealbreakers
# Requirements a model must never wave away as "soft": they're checkable facts about a candidate.
HARD = re.compile(r"\d+\s*\+?\s*(years?|yrs)|\bdegree\b|bachelor|master'?s|ph\.?d", re.IGNORECASE)


async def judge_requirements(requirements: list[str], candidate, judge) -> ScoreResult | None:
    """Judge each requirement against the candidate. Soft skills are listed but not scored."""
    reqs = unique(requirements)
    if not reqs:
        return None
    met, partial, missing, soft = [], [], [], []
    for req in reqs:
        verdict = await judge(req, candidate)
        if verdict is None and HARD.search(req):
            verdict = 0.0
        bucket = soft if verdict is None else met if verdict == 1.0 else partial if verdict == 0.5 else missing
        bucket.append(req)
    scored = len(met) + len(partial) + len(missing)
    if scored == 0:
        return None
    score = round((len(met) + 0.5 * len(partial)) / (scored + SMOOTHING), 2)
    if any(REQUIRED.search(m) for m in missing):
        score = 0.0                                   # missing a stated dealbreaker
    return ScoreResult(score=score, met=met, partial=partial, missing=missing, soft=soft)


def profile_text(skills: list[str] | None, education: list[str] | None, experience: list[str] | None) -> str:
    """The candidate as the judge sees it: one line per section that has content."""
    lines = [f"Skills: {', '.join(skills or [])}"]
    if education:
        lines.append("Education: " + "; ".join(education))
    if experience:
        lines.append("Experience: " + "; ".join(experience))
    return "\n".join(lines)
