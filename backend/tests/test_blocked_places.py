from app.db.models_db import Job
from app.services.preferences_services import Preferences, allowed


def job(location):
    return Job(title="Software Engineer", location=location)


def test_jobs_only_in_a_blocked_place_never_show():
    assert not allowed(job("Tel Aviv, Israel"), Preferences())
    assert not allowed(job("Tel Aviv"), Preferences(locations=["remote"]))


def test_other_locations_of_the_same_job_still_count():
    assert allowed(job("New York, NY; Tel Aviv, Israel"), Preferences())
    assert allowed(job("New York, NY; Tel Aviv, Israel"), Preferences(locations=["new york city"]))


def test_a_blocked_place_is_never_the_reason_a_job_matches():
    assert not allowed(job("New York, NY; Tel Aviv, Israel"), Preferences(locations=["israel"]))
