from uuid import uuid4
from app.schemas.matches_schemas import MatchOut
from app.services import digest_services as digest


def m(title, score):
    return MatchOut(job_id=uuid4(), title=title, score=score)


def test_digest_lists_top_matches_best_first():
    matches = [m("Data", 0.6), m("Backend", 0.9), m("Platform", 0.8)]

    body = digest.render(matches, top_n=2)

    assert body.index("Backend") < body.index("Platform")
    assert "Data" not in body


def test_digest_with_no_matches_says_so():
    assert "no new matches" in digest.render([], top_n=5).lower()