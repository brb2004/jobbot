from app.services.matcher_services import match

VECTORS = {"databases": [1.0, 0.1, 0.0], "postgresql": [0.9, 0.2, 0.0], "react": [0.0, 1.0, 0.0],
           "c": [0.0, 0.0, 1.0], "rust": [0.1, 0.0, 0.9]}


class FakeJudge:
    def __init__(self, yes=()):
        self.yes = set(yes)
        self.asked = []

    async def __call__(self, requirement, skill):
        self.asked.append((requirement, skill))
        return (requirement, skill) in self.yes


async def test_exact_match_never_asks_the_judge():
    judge = FakeJudge()
    r = await match(["Python"], ["python"], judge=judge)
    assert r.met == ["Python"]
    assert judge.asked == []


async def test_judge_yes_counts_as_met_with_that_skill_as_evidence():
    judge = FakeJudge(yes={("Databases", "PostgreSQL")})
    r = await match(["Databases"], ["PostgreSQL", "React"], VECTORS, judge)
    assert r.met == ["Databases"]
    assert r.evidence == {"Databases": "PostgreSQL"}


async def test_judge_no_means_missing_even_if_vectors_are_close():
    r = await match(["Rust"], ["C"], VECTORS, FakeJudge())       # close vectors, judge says no
    assert r.missing == ["Rust"]
    assert r.score == 0.0


async def test_judge_only_sees_the_nearest_candidates_nearest_first():
    judge = FakeJudge()
    await match(["Databases"], ["PostgreSQL", "React", "C"], VECTORS, judge, candidates=2)
    assert judge.asked == [("Databases", "PostgreSQL"), ("Databases", "React")]


async def test_without_a_judge_only_exact_matches_count():
    r = await match(["Databases"], ["PostgreSQL"], VECTORS)
    assert r.missing == ["Databases"]


async def test_duplicate_requirements_count_once():
    assert (await match(["Docker", "docker"], ["Docker"])).score == 1.0


async def test_no_requirements_gives_no_score():
    assert await match([], ["Python"]) is None
