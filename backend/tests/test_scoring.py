from app.services.scoring_services import idf_weights, score_job, top_matches


def test_rare_skills_weigh_more():
    w = idf_weights([{"Python", "Go"}, {"Python"}, {"Python", "Rust"}])
    assert w["Python"] < w["Go"] == w["Rust"]


def test_score_is_weighted_coverage_of_the_job():
    w = {"Python": 1.0, "Kubernetes": 3.0}
    job = {"Python", "Kubernetes"}
    assert score_job("j", job, {"Python"}, w).score == 0.25
    assert score_job("j", job, {"Kubernetes"}, w).score == 0.75
    assert score_job("j", job, {"Python", "Kubernetes", "Rust"}, w).score == 1.0


def test_explanation_lists_heaviest_skills_first():
    m = score_job("j", {"A", "B", "C"}, {"C"}, {"A": 1.0, "B": 3.0, "C": 2.0})
    assert m.matched == ["C"]
    assert m.missing == ["B", "A"]


def test_job_without_skills_cannot_be_scored():
    assert score_job("j", set(), {"Python"}, {}) is None


def test_top_matches_ranks_skips_unrelated_jobs_and_breaks_ties_by_id():
    jobs = {"j1": {"Python"}, "j2": {"Python", "Go"}, "j3": {"Rust"}, "j4": {"Python"}}
    w = {"Python": 1.0, "Go": 1.0, "Rust": 1.0}
    assert [m.job_id for m in top_matches({"Python"}, jobs, w, k=10)] == ["j1", "j4", "j2"]
    assert [m.job_id for m in top_matches({"Python"}, jobs, w, k=2)] == ["j1", "j4"]
    assert top_matches(set(), jobs, w) == []
