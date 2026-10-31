from app.db.models_db import Job
from app.services.preferences_services import Preferences, allowed

PREFS = Preferences(exclude_titles=["intern", "senior", "staff", "principal", "sr."])


def test_excluded_title_words_filter_out_jobs():
    assert not allowed(Job(title="Software Engineer Intern"), PREFS)
    assert not allowed(Job(title="Senior Production Engineer"), PREFS)
    assert not allowed(Job(title="Sr. Backend Engineer"), PREFS)
    assert allowed(Job(title="Software Engineer"), PREFS)


def test_matches_whole_words_only():
    assert allowed(Job(title="Internal Tools Engineer"), PREFS)              # "intern" inside "Internal"


def test_no_preferences_allows_everything():
    assert allowed(Job(title="Senior Staff Principal Intern"), Preferences())
