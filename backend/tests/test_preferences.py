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


def test_no_preferences_means_engineering_roles_only():
    assert allowed(Job(title="Senior Staff Principal Engineer"), Preferences())
    assert not allowed(Job(title="Senior Staff Principal Intern"), Preferences())


def test_include_titles_require_one_of_the_words():
    prefs = Preferences(include_titles=["engineer", "developer"])
    assert allowed(Job(title="IT Systems Engineer"), prefs)
    assert not allowed(Job(title="Account Executive, Platforms"), prefs)
    assert not allowed(Job(title="Anything"), Preferences())      # no include list = engineering default


def test_exclude_wins_over_include():
    prefs = Preferences(include_titles=["engineer"], exclude_titles=["sr"])
    assert not allowed(Job(title="Sr Software Engineer"), prefs)


def test_locations_require_one_of_the_words():
    prefs = Preferences(locations=["remote", "dallas"])
    assert allowed(Job(title="Engineer", location="Remote - US"), prefs)
    assert allowed(Job(title="Engineer", location="Dallas, TX"), prefs)
    assert not allowed(Job(title="Engineer", location="San Francisco, CA"), prefs)
    assert not allowed(Job(title="Engineer", location=None), prefs)          # unknown location: not shown
    assert allowed(Job(title="Engineer", location="Anywhere"), Preferences())


def test_remote_jobs_must_be_in_an_allowed_region():
    prefs = Preferences(locations=["remote", "dallas"], remote_regions=["us", "usa", "united states"])
    assert allowed(Job(title="Engineer", location="Remote - United States"), prefs)
    assert allowed(Job(title="Engineer", location="Remote- USA"), prefs)
    assert allowed(Job(title="Engineer", location="San Francisco, CA, US; Remote, US"), prefs)
    assert allowed(Job(title="Engineer", location="Remote, Canada; Remote, United States"), prefs)
    assert allowed(Job(title="Engineer", location="Dallas, TX"), prefs)
    assert allowed(Job(title="Engineer", location="Remote"), prefs)
    assert not allowed(Job(title="Engineer", location="Remote - Mexico"), prefs)
    assert not allowed(Job(title="Engineer", location="Remote, Poland"), prefs)
