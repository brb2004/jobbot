from app.llm.scorer_llm import ScoreResult, unique


async def judge_requirements(requirements: list[str], skills: list[str], judge) -> ScoreResult | None:
    """Ask the judge about each requirement against the whole skills list. yes=1, partial=0.5, no=0."""
    reqs = unique(requirements)
    if not reqs:
        return None
    met, partial, missing = [], [], []
    for req in reqs:
        verdict = await judge(req, skills)
        (met if verdict == 1.0 else partial if verdict == 0.5 else missing).append(req)
    score = round((len(met) + 0.5 * len(partial)) / len(reqs), 2)
    return ScoreResult(score=score, met=met, partial=partial, missing=missing)
