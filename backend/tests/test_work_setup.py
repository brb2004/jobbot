import pytest
from pydantic import ValidationError

from app.db.models_db import Job
from app.services.preferences_services import Preferences, allowed


def job(location):
    return Job(title="Software Engineer", location=location)


def test_remote_jobs_count_when_open_to_where_you_are():
    p = Preferences(locations=["dallas"])
    for loc in ("Remote - US", "Remote, United States", "Remote - North America", "Remote", "Plano, TX"):
        assert allowed(job(loc), p), loc
    for loc in ("Remote - Mexico", "Remote - Canada", "Remote, Poland", "Austin, TX"):
        assert not allowed(job(loc), p), loc


def test_no_remote():
    p = Preferences(locations=["dallas"], remote=False)
    assert allowed(job("Plano, TX"), p)
    assert not allowed(job("Remote - US"), p)
    assert allowed(job("Plano, TX; Remote, US"), p)  # the on-site part still counts


def test_remote_only():
    p = Preferences(locations=["dallas"], onsite=False)
    assert allowed(job("Remote - US"), p)
    assert not allowed(job("Plano, TX"), p)


def test_remote_anywhere_in_a_region():
    p = Preferences(locations=["europe"], onsite=False)
    assert allowed(job("Remote - Germany"), p)
    assert not allowed(job("Remote - US"), p)


def test_one_switch_has_to_stay_on():
    with pytest.raises(ValidationError):
        Preferences(remote=False, onsite=False)


def test_old_saved_preferences_convert():
    remote_only = Preferences.model_validate({"locations": ["remote"], "remote_regions": ["us"]})
    assert (remote_only.locations, remote_only.remote, remote_only.onsite) == (["us"], True, False)
    both = Preferences.model_validate({"locations": ["remote", "dallas"], "remote_regions": ["us"]})
    assert (both.locations, both.remote, both.onsite) == (["dallas"], True, True)
