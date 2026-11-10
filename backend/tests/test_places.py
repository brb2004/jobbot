from app.db.models_db import Job
from app.services.places_services import place_of, places_in
from app.services.preferences_services import Preferences, allowed


def job(location):
    return Job(title="Software Engineer", location=location)


def test_the_places_file_loads_and_resolves_containment():
    assert places_in("Plano, TX") >= {"Dallas-Fort Worth", "United States", "North America"}
    assert place_of("united states of america") == place_of("usa") == place_of("america") == "United States"


def test_every_spelling_of_the_us_counts_as_the_us():
    prefs = Preferences(locations=["remote"], remote_regions=["united states of america"])
    for loc in ("Remote - USA", "Remote US", "United States (Remote)", "Remote, United States", "United States - Remote"):
        assert allowed(job(loc), prefs), loc
    assert not allowed(job("Remote - Canada"), prefs)


def test_america_is_not_latin_america():
    prefs = Preferences(locations=["remote"], remote_regions=["america"])
    assert allowed(job("Remote - United States"), prefs)
    assert not allowed(job("Remote - Latin America"), prefs)


def test_a_metro_covers_its_suburbs():
    prefs = Preferences(locations=["dallas"])
    for loc in ("Plano, TX", "Richardson, Texas", "Irving, TX, United States"):
        assert allowed(job(loc), prefs), loc
    assert not allowed(job("Austin, TX"), prefs)


def test_a_country_covers_its_cities():
    prefs = Preferences(locations=["united states"])
    assert allowed(job("San Mateo, CA United States"), prefs)
    assert allowed(job("Mountain View, California (HQ)"), prefs)
    assert not allowed(job("Toronto, Canada"), prefs)


def test_distributed_counts_as_remote():
    assert allowed(job("Distributed"), Preferences(locations=["remote"]))


def test_unknown_words_still_match_like_before():
    assert allowed(job("Springfield, IL"), Preferences(locations=["springfield"]))
