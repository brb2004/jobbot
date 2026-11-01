from app.services.scoring_services import idf_weights, score_job, top_matches


def test_rare_skills_weigh_more():
    w = idf_weights([{"Python", "Go"}, {"Python"}, {"Python", "Rust"}])
    assert w["Python"] < w["Go"] == w["Rust"]


def test_score_is_weighted_coverage_of_the_job():
    w = {"Python": 1.0, "Kubernetes": 3.0}
    job = {"Python", "Kubernetes"}
    assert score_job("j", job, {"Python"}, w, prior=0).score == 0.25
    assert score_job("j", job, {"Kubernetes"}, w, prior=0).score == 0.75
    assert score_job("j", job, {"Python", "Kubernetes", "Rust"}, w, prior=0).score == 1.0


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


def test_thin_jobs_are_pulled_down():
    w = {"APIs": 1.0, "Python": 1.0, "React": 1.0}
    me = {"APIs", "Python", "React"}
    thin = score_job("t", {"APIs"}, me, w).score                       # 1 / (1 + 2)
    thick = score_job("k", {"APIs", "Python", "React"}, me, w).score   # 3 / (3 + 2)
    assert thin < thick < 1.0


def test_prior_is_measured_in_average_skills_so_scale_doesnt_matter():
    small = score_job("j", {"A"}, {"A"}, {"A": 1.0}).score     # 1 / (1 + 2*1)
    big = score_job("j", {"A"}, {"A"}, {"A": 5.0}).score       # 5 / (5 + 2*5)
    assert small == big == 0.33
