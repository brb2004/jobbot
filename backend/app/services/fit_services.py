from app.llm.scorer_llm import ScoreResult, unique


async def judge_requirements(requirements: list[str], skills: list[str], judge) -> ScoreResult | None:
    """Judge each requirement against the whole skills list. Soft skills are listed but not scored."""
    reqs = unique(requirements)
    if not reqs:
        return None
    met, partial, missing, soft = [], [], [], []
    for req in reqs:
        verdict = await judge(req, skills)
        bucket = soft if verdict is None else met if verdict == 1.0 else partial if verdict == 0.5 else missing
        bucket.append(req)
    scored = len(met) + len(partial) + len(missing)
    if scored == 0:
        return None                                   # only soft skills: nothing a resume can be measured on
    score = round((len(met) + 0.5 * len(partial)) / scored, 2)
    return ScoreResult(score=score, met=met, partial=partial, missing=missing, soft=soft)
