from app.services.requirements_services import years_from_title, years_note, years_required
from app.services.scoring_services import TITLE_CAP, idf_weights, score_job, top_matches


def test_rare_skills_weigh_more():
    w = idf_weights([{"Python", "Go"}, {"Python"}, {"Python", "Rust"}])
    assert w["Python"] < w["Go"] == w["Rust"]


def test_score_is_weighted_coverage_of_the_job():
    w = {"SQL": 1.0, "Kubernetes": 3.0}
    job = {"SQL", "Kubernetes"}
    assert score_job("j", job, {"SQL"}, w, prior=0).score == 0.25
    assert score_job("j", job, {"Kubernetes"}, w, prior=0).score == 0.75
    assert score_job("j", job, {"SQL", "Kubernetes", "Rust"}, w, prior=0).score == 1.0


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
    thin = score_job("t", {"APIs"}, me, w).score
    thick = score_job("k", {"APIs", "Python", "React"}, me, w).score
    assert thin < thick < 1.0


def test_prior_is_measured_in_average_skills_so_scale_doesnt_matter():
    small = score_job("j", {"A"}, {"A"}, {"A": 1.0}).score
    big = score_job("j", {"A"}, {"A"}, {"A": 5.0}).score
    assert small == big == 0.33


def test_years_required_uses_each_asks_floor_and_the_max_across_bullets():
    assert (
        years_required(["3+ years of Go", "2–12+ years of experience", "5-7 yrs in prod", "no number"]) == 5
    )
    assert years_required(["Python", "Strong SQL"]) is None


def test_over_asking_jobs_are_halved_and_flagged():
    w = {"Python": 1.0}
    asked = score_job("j", {"Python"}, {"Python"}, w, prior=0, job_years=4, user_years=1)
    close = score_job("j", {"Python"}, {"Python"}, w, prior=0, job_years=2, user_years=1)
    unknown = score_job("j", {"Python"}, {"Python"}, w, prior=0, job_years=5, user_years=None)
    assert (asked.score, asked.years_asked, asked.over_years) == (0.5, 4, True)
    assert (close.score, close.years_asked, close.over_years) == (1.0, 2, False)
    assert (unknown.score, unknown.years_asked, unknown.over_years) == (
        1.0,
        5,
        False,
    )


def test_top_matches_applies_allow_filter_only_to_candidates():
    jobs = {"j1": {"Python"}, "j2": {"Python"}, "j3": {"Rust"}}
    seen = []

    def allow(j):
        return seen.append(j) or j != "j1"

    result = top_matches({"Python"}, jobs, {"Python": 1.0, "Rust": 1.0}, allow=allow)
    assert [m.job_id for m in result] == ["j2"]
    assert "j3" not in seen


def test_allow_is_only_checked_until_k_matches_pass():
    jobs = {f"j{i}": {"Python"} for i in range(1, 6)}
    seen = []

    def allow(j):
        return seen.append(j) or j != "j1"

    result = top_matches({"Python"}, jobs, {"Python": 1.0}, k=2, allow=allow)
    assert [m.job_id for m in result] == ["j2", "j3"]
    assert seen == ["j1", "j2", "j3"]


def test_within_restricts_candidates_before_scoring():
    jobs = {"j1": {"Python"}, "j2": {"Python"}, "j3": {"Python"}}
    result = top_matches({"Python"}, jobs, {"Python": 1.0}, within={"j2", "j3"})
    assert [m.job_id for m in result] == ["j2", "j3"]


def test_dedupe_key_keeps_only_the_best_posting_per_key():
    jobs = {"j1": {"Python"}, "j2": {"Python"}, "j3": {"Python"}}
    keys = {"j1": ("stripe", "backend"), "j2": ("stripe", "backend"), "j3": ("stripe", "frontend")}
    result = top_matches({"Python"}, jobs, {"Python": 1.0}, dedupe_key=keys)
    assert [m.job_id for m in result] == ["j1", "j3"]


def test_years_from_title_when_the_posting_gives_no_number():
    assert years_from_title("Senior Backend Engineer") == 5
    assert years_from_title("Sr. Engineer") == 5
    assert years_from_title("Staff Software Engineer") == 8
    assert years_from_title("Principal Engineer") == 10
    assert years_from_title("Software Engineer II") == 2


def test_years_note_wording():
    assert years_note({"years_asked": 3}) == "asks for 3+ years"
    assert years_note({"years_asked": 5, "years_source": "title"}) == "senior-level title (~5+ years)"
    assert years_note({}) is None


def test_years_in_education_clauses_are_not_work_experience():
    assert years_required(["At least 1 year of university education, or equivalent work experience."]) is None
    assert (
        years_required(
            [
                "Must be currently enrolled in an accredited Bachelor's degree program or within 1 year of graduation"
            ]
        )
        is None
    )
    assert years_required(["2+ years of coursework in data structures"]) is None
    assert years_required(["5+ years of auditing experience, including IT/Information Security."]) == 5
    assert years_required(["Degree in CS, plus 3+ years of industry experience"]) == 3


def test_at_most_n_picks_per_company():
    jobs = {f"a{i}": {"Python"} for i in range(5)} | {"b1": {"Python"}, "b2": {"Python"}}
    company = {j: j[0] for j in jobs}
    out = top_matches({"Python"}, jobs, {"Python": 1.0}, k=10, company=company, per_company=2)
    picked = [m.job_id[0] for m in out]
    assert picked.count("a") == 2 and picked.count("b") == 2 and len(out) == 4


def test_a_skill_in_the_title_outweighs_the_stack_list():
    stack = {"Python", "Docker", "Linux", "C", "GitHub Actions"}
    me = stack | {"LLMs & Generative AI"}
    weights = dict.fromkeys(stack | {"Reinforcement Learning", "LLMs & Generative AI"}, 1.0)
    plain = score_job("j", stack, me, weights)
    rl = score_job("j", stack, me, weights, core=frozenset({"Reinforcement Learning"}))
    assert rl.score < plain.score and rl.score <= TITLE_CAP
    assert rl.missing[0] == "Reinforcement Learning"


def test_having_the_title_skill_helps():
    weights = dict.fromkeys({"Python", "Machine Learning", "Docker", "Go"}, 1.0)
    job = {"Python", "Docker", "Go"}
    me = {"Python", "Machine Learning"}
    plain = score_job("j", job, me, weights)
    ml = score_job("j", job, me, weights, core=frozenset({"Machine Learning"}))
    assert ml.score > plain.score
