from app.db.models_db import Job
from app.services.preferences_services import Preferences, allowed
from app.services.requirements_services import needs_clearance
from app.services.scoring_services import TIERS, score_job


def test_support_and_teaching_roles_are_out_by_default():
    for title in (
        "Support Engineer",
        "Senior Support Engineer, Americas",
        "Technical Curriculum Developer",
        "Creative Engineer",
        "Enterprise Engineer",
    ):
        assert not allowed(Job(title=title), Preferences()), title
    assert allowed(Job(title="Software Engineer"), Preferences())
    assert allowed(Job(title="Site Reliability Engineer"), Preferences())


def test_only_naming_the_role_brings_it_back():
    assert allowed(Job(title="Support Engineer"), Preferences(include_titles=["support engineer"]))
    assert not allowed(Job(title="Support Engineer"), Preferences(include_titles=["engineer", "developer"]))


def test_missing_every_language_the_job_names_caps_below_strong():
    w = {s: 1.0 for s in ("Ruby", "Ruby on Rails", "SQL", "Git", "Docker", "Python")}
    m = score_job(
        "j", {"Ruby", "Ruby on Rails", "SQL", "Git", "Docker"}, {"SQL", "Git", "Docker", "Python"}, w, prior=0
    )
    assert m.no_language and m.score < TIERS[0][0]  # 3/5 = 0.6 uncapped


def test_one_of_the_named_languages_is_enough():
    w = {"Python": 1.0, "Go": 1.0, "SQL": 1.0}
    m = score_job("j", {"Python", "Go", "SQL"}, {"Python", "SQL"}, w, prior=0)
    assert not m.no_language and m.score == round(2 / 3, 2)


def test_jobs_far_above_your_years_are_dropped():
    w = {"Python": 1.0}
    assert score_job("j", {"Python"}, {"Python"}, w, job_years=4, user_years=0) is None
    m = score_job("j", {"Python"}, {"Python"}, w, job_years=3, user_years=0)
    assert m is not None and m.over_years  # +3 still shows, halved


def test_clearance_and_citizenship_asks_are_flagged():
    assert needs_clearance("U.S. Government Support", [])
    assert needs_clearance("Software Engineer", ["Must be a U.S. citizen", "Python"])
    assert needs_clearance("Engineer", ["Active Secret clearance required"])
    assert not needs_clearance("Software Engineer", ["Python, Go", "Clear communication skills"])
