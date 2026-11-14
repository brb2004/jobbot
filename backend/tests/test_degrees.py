from app.ingest.degree_ingest import ASSOCIATE, BACHELOR, MASTER, NONE, PHD, bullet_degree, required_degree
from app.services.preferences_services import Preferences, degree_ok


def page(heading: str, *bullets: str) -> str:
    return f"<h3>{heading}</h3><ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"


def test_a_required_degree_is_read_from_the_requirements():
    assert (
        required_degree(page("Requirements", "Bachelor's degree in Computer Science", "Python")) == BACHELOR
    )
    assert required_degree(page("Qualifications", "PhD in Machine Learning")) == PHD
    assert required_degree(page("What you'll bring", "BS or MS in a technical field")) == BACHELOR


def test_escape_hatches_never_count():
    for text in (
        "Bachelor's degree in CS or equivalent experience",
        "BS in Computer Science or 4+ years of experience",
        "Master's degree preferred",
        "Currently pursuing a bachelor's degree",
        "A degree in CS is a plus",
    ):
        assert bullet_degree(text) == NONE, text


def test_preferred_sections_never_count():
    html = page("Requirements", "3+ years of Python") + page(
        "Preferred qualifications", "Master's degree in CS"
    )
    assert required_degree(html) == NONE
    assert required_degree(page("Nice to have", "PhD")) == NONE


def test_only_requirement_sections_count():
    assert required_degree(page("About us", "Founded by people with a Master's degree")) == NONE
    assert required_degree(None) == NONE


def test_the_education_preference_hides_only_higher_degrees():
    mine = Preferences(education="associate")
    assert degree_ok(ASSOCIATE, mine) and degree_ok(None, mine)
    assert not degree_ok(BACHELOR, mine) and not degree_ok(MASTER, mine)
    assert degree_ok(PHD, Preferences())


def test_ms_office_is_not_a_masters():
    assert bullet_degree("Comfortable with MS Office and Excel") == NONE
    assert bullet_degree("MS in Statistics") == MASTER
