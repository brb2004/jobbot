from app.db.models_db import Job
from app.services.preferences_services import Preferences, allowed
from app.services.titles_services import role_key


def test_location_suffixes_collapse_to_one_role():
    a = role_key("Senior Engineering Manager, Grafana Frontend - USA")
    assert a == role_key("Senior Engineering Manager, Grafana Frontend | UK")
    assert a == role_key("Senior Engineering Manager, Grafana Frontend (Germany)")
    assert a == role_key("Senior Engineering Manager, Grafana Frontend - Remote, Canada")


def test_punctuation_differences_collapse():
    assert role_key("Systems Engineer (Data Intelligence & Analytics Team)") == \
           role_key("Systems Engineer, Data Intelligence & Analytics Team")


def test_real_differences_stay_different():
    assert role_key("Software Engineer - Backend") != role_key("Software Engineer - Frontend")
    assert role_key("Senior Engineer - US Payments") != role_key("Senior Engineer - Payments")


def test_go_does_not_match_go_to_market():
    prefs = Preferences(include_titles=["go"])
    assert not allowed(Job(title="Revenue and Go-to-Market Accounting Lead"), prefs)
    assert allowed(Job(title="Go Developer"), prefs)


def test_no_include_list_defaults_to_engineering_roles():
    prefs = Preferences()
    assert allowed(Job(title="Backend Engineer"), prefs)
    assert allowed(Job(title="Site Reliability Engineer (SRE)"), prefs)
    assert not allowed(Job(title="Staff Product Manager, Sail Core"), prefs)
    assert not allowed(Job(title="Senior Onchain Investigator"), prefs)
    assert allowed(Job(title="Staff Product Manager"), Preferences(include_titles=["product manager"]))


def test_hyphenated_remote_locations_still_match():
    prefs = Preferences(locations=["remote"])
    assert allowed(Job(title="Engineer", location="Chicago, US-Remote"), prefs)


def test_city_suffixes_collapse():
    a = role_key("Software Engineer - New Grad (2027 Start) - Aarhus")
    assert a == role_key("Software Engineer - New Grad (2027 Start) - Berlin")
    assert a == role_key("Software Engineer - New Grad (2027 Start) - Amsterdam")


def test_title_synonyms_collapse_but_teams_stay_apart():
    assert role_key("Principal Software Developer - Vector Search - Elasticsearch") == \
           role_key("Principal Software Engineer - Vector Search - Elasticsearch")
    assert role_key("Sr. Backend Engineer") == role_key("Senior Backend Engineer")
    assert role_key("Principal Software Engineer - Vector Search - Elasticsearch") != \
           role_key("Principal Software Engineer - Search Algorithms - Elasticsearch")


def test_presales_roles_are_excluded_unless_opted_in():
    default = Preferences()
    for title in ("Enterprise Sales Engineer", "Presales Customer Engineer", "Senior Solutions Architect",
                  "Major Account Executive, France"):
        assert not allowed(Job(title=title), default), title
    assert allowed(Job(title="Salesforce Developer"), default)          # whole words: not "sales"
    assert allowed(Job(title="Backend Engineer"), default)
    opted = Preferences(include_presales=True)
    assert allowed(Job(title="Enterprise Sales Engineer"), opted)
    assert allowed(Job(title="Senior Solutions Architect"), opted)
