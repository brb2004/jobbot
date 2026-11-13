from app.services.skill_gaps import candidates, rank
from app.services.skills_services import Tagger

T = Tagger.from_text("Python\nGitHub Actions\nKubernetes: k8s\nPostgreSQL: postgres\n")


def test_finds_unknown_tech_words_and_skips_known_ones():
    got = candidates("Experience with Python, SQLAlchemy and JWT auth on Kubernetes", T)
    assert {"SQLAlchemy", "JWT"} <= got
    assert not got & {"Python", "Kubernetes", "Experience"}


def test_known_multiword_skills_leave_nothing_behind():
    assert "Actions" not in candidates("CI with GitHub Actions and Terraform", T)
    assert "Terraform" in candidates("CI with GitHub Actions and Terraform", T)


def test_symbols_digits_pairs_and_sentence_starts():
    got = candidates("Strong Node.js, C# and x86-64 skills; Spring Boot or Google Cloud a plus", T)
    assert {"Node.js", "C#", "x86-64", "Spring Boot", "Google Cloud"} <= got
    assert "Strong" not in got  # capitalised only because it starts the bullet


def test_ranked_by_companies_not_by_one_company_repeating_itself():
    rows = [("acme", ["Use AcmeOS daily"])] * 50 + [(c, ["Know Snowflake"]) for c in ("a", "b", "c")]
    ranked = rank(rows, T, min_companies=3)
    assert [r[0] for r in ranked] == ["Snowflake"]  # AcmeOS: 50 postings, but 1 company
    assert ranked[0][1:3] == (3, 3)


def test_slash_joined_plain_words_are_not_terms():
    got = candidates("Experience with SQLAlchemy and/or Kafka; CI/CD a plus", T)
    assert "and/or" not in got and {"SQLAlchemy", "Kafka", "CI/CD"} <= got
