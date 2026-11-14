from types import SimpleNamespace

from app.services.job_index_services import _years
from app.services.pay_level_services import years_from_pay
from app.services.requirements_services import seniority_pitch, years_from_pitch, years_from_title, years_note


def test_level_numbers_in_titles_imply_years():
    assert years_from_title("Software Engineer II - CIAM") == 2
    assert years_from_title("Software Engineer 2, Payments") == 2
    assert years_from_title("Software Engineer III") == 4
    assert years_from_title("SDE IV") == 6


def test_entry_level_and_lookalikes_imply_nothing():
    assert years_from_title("Software Engineer I, Fullstack (Search)") is None
    assert years_from_title("University Grad Software Engineer 2027 (USA)") is None
    assert years_from_title("Platform Engineer, World War II Archive") is None


def test_seniority_words_beat_level_numbers():
    assert years_from_title("Senior Software Engineer II") == 5


def test_note_says_mid_or_senior():
    assert years_note({"years_asked": 2, "years_source": "title"}) == "mid-level title (~2+ years)"
    assert years_note({"years_asked": 5, "years_source": "title"}) == "senior-level title (~5+ years)"


def test_architect_titles_are_senior():
    from app.services.requirements_services import years_from_title

    assert years_from_title("AI Architect") == 5
    assert years_from_title("Solutions Architect (FedS062)") == 5
    assert years_from_title("Principal Architect") == 10
    assert years_from_title("Software Engineer, Architecture Tooling") is None


def test_a_senior_role_named_only_in_the_summary_is_still_senior():
    text = (
        "We're looking for a Senior/Staff Offensive Security Software Engineer with deep pentest experience."
    )
    pitch = seniority_pitch(text)
    assert years_from_pitch([pitch]) == 5
    assert years_note({"years_asked": 5, "years_source": "pitch"}) == "senior-level role (~5+ years)"


def test_ordinary_text_has_no_seniority_pitch():
    assert seniority_pitch("We're looking for engineers who love senior citizens' apps.") is None
    assert seniority_pitch("Lead the design of our APIs.") is None


def test_the_title_wins_over_the_summary():
    row = SimpleNamespace(title="Staff Engineer", requirements=["looking for a senior engineer"])
    assert _years(row) == (8, "title")


def test_experienced_in_the_summary_means_mid_level():
    pitch = seniority_pitch(
        "We're looking for an experienced full-stack Documentation Platform Engineer to evolve"
    )
    assert years_from_pitch([pitch]) == 3
    assert years_from_pitch([seniority_pitch("looking for a Senior/Staff engineer")]) == 5


def test_the_pay_floor_hints_at_level_unless_the_title_says_junior():
    assert years_from_pay("Machine Learning Engineer", 175_000, "USD") == 3
    assert years_from_pay("Applied AI Engineer", 204_400, "USD") == 5
    assert years_from_pay("Software Engineer", 120_000, "USD") is None
    assert years_from_pay("Software Engineer, New Grad", 190_000, "USD") is None
    assert years_from_pay("Marketing Engineer I", 190_000, "USD") is None
    assert years_from_pay("Software Engineer", 190_000, "EUR") is None


def test_the_pay_floor_is_the_last_resort():
    row = SimpleNamespace(
        title="Engineer", requirements=["3+ years of Python"], salary_min=200_000, salary_currency="USD"
    )
    assert _years(row) == (3, "requirements")
    row = SimpleNamespace(title="Engineer", requirements=[], salary_min=200_000, salary_currency="USD")
    assert _years(row) == (5, "pay")
    assert years_note({"years_asked": 5, "years_source": "pay"}) == "pay suggests ~5+ years"
