import math

from app.llm.scorer_llm import ScoreResult, normalize, unique

CANDIDATES = 3            # how many nearest skills the judge may look at per requirement


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def nearest(req_key: str, have: dict[str, str], vectors: dict[str, list[float]], n: int) -> list[str]:
    """Your n skills closest in meaning to the requirement. Ranking only; never decides by itself."""
    if req_key not in vectors:
        return []
    ranked = sorted(((cosine(vectors[req_key], vectors[k]), skill) for k, skill in have.items() if k in vectors),
                    reverse=True)
    return [skill for _, skill in ranked[:n]]


async def match(requirements: list[str], skills: list[str], vectors=None, judge=None,
                candidates: int = CANDIDATES) -> ScoreResult | None:
    reqs = unique(requirements)
    if not reqs:
        return None
    vectors = vectors or {}
    have = {normalize(s): s for s in skills}

    met, missing, evidence = [], [], {}
    for req in reqs:
        key = normalize(req)
        if key in have:                                            # 1. exact: free
            met.append(req)
            evidence[req] = have[key]
            continue
        found = None
        if judge is not None:                                      # 2. retrieve, then judge
            for skill in nearest(key, have, vectors, candidates):
                if await judge(req, skill):
                    found = skill
                    break
        if found:
            met.append(req)
            evidence[req] = found
        else:
            missing.append(req)
    return ScoreResult(score=round(len(met) / len(reqs), 2), met=met, missing=missing, evidence=evidence)
