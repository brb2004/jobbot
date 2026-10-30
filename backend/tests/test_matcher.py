from app.services.matcher_services import match

# Hand-made 3-number "embeddings": observability and prometheus point the same way; go and python don't.
VECTORS = {
    "observability": [1.0, 0.0, 0.0],
    "prometheus":    [0.9, 0.1, 0.0],
    "go":            [0.0, 1.0, 0.0],
    "python":        [0.0, 0.0, 1.0],
}


def test_exact_match_needs_no_vectors():
    r = match(["Python", "Go"], ["python"])
    assert r.met == ["Python"]
    assert r.missing == ["Go"]
    assert r.score == 0.5


def test_similar_meaning_matches_and_records_which_skill():
    r = match(["Observability"], ["Prometheus"], VECTORS)
    assert r.met == ["Observability"]
    assert r.evidence == {"Observability": "Prometheus"}


def test_unrelated_meaning_does_not_match():
    r = match(["Go"], ["Python"], VECTORS)
    assert r.missing == ["Go"]
    assert r.score == 0.0


def test_duplicate_requirements_count_once():
    assert match(["Docker", "docker"], ["Docker"]).score == 1.0


def test_no_requirements_gives_no_score():
    assert match([], ["Python"]) is None