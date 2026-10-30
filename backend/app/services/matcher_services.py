import math

from app.llm.scorer_llm import ScoreResult, normalize, unique

THRESHOLD = 0.80          # how similar two terms must be to count as the same skill (tune on real data)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def match(requirements: list[str], skills: list[str],
          vectors: dict[str, list[float]] | None = None, threshold: float = THRESHOLD) -> ScoreResult | None:
    reqs = unique(requirements)
    if not reqs:
        return None
    vectors = vectors or {}
    have = {normalize(s): s for s in skills}

    met, missing, evidence = [], [], {}
    for req in reqs:
        key = normalize(req)
        if key in have:                                   # 1. exact match: free
            met.append(req)
            evidence[req] = have[key]
            continue
        best, best_sim = None, 0.0                        # 2. closest skill by meaning
        if key in vectors:
            for skill_key, skill in have.items():
                if skill_key in vectors:
                    sim = cosine(vectors[key], vectors[skill_key])
                    if sim > best_sim:
                        best, best_sim = skill, sim
        if best is not None and best_sim >= threshold:
            met.append(req)
            evidence[req] = best                          # "met because you have Prometheus"
        else:
            missing.append(req)

    return ScoreResult(score=round(len(met) / len(reqs), 2), met=met, missing=missing, evidence=evidence)