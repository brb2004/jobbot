import pytest

from app.db.models_db import Job
from app.services.experience_services import years_from_resume
from app.services.preferences_services import Preferences, allowed
from app.services.requirements_services import years_required
from app.services.title_rules_services import title_ok

DEFAULT = Preferences()


@pytest.mark.parametrize(
    "title",
    [
        "Senior Software Engineer, Sales Platform",
        "Backend Engineer - Sales Tools",
        "Software Engineer, Customer Success Tooling",
        "Software Engineer, Hardware Platform",
        "Full Stack Engineer, Technical Support Systems",
        "Salesforce Developer",
    ],
)
def test_titles_that_build_software_are_shown(title):
    assert allowed(Job(title=title), DEFAULT)


@pytest.mark.parametrize(
    "title",
    [
        "Enterprise Sales Engineer",
        "Presales Customer Engineer",
        "Senior Solutions Architect",
        "Sales Engineer, Developer Tools",
        "Customer Success Engineer",
        "Senior Hardware Engineer",
        "Electrical Engineer II",
        "Mechanical Engineer, Robotics",
        "ASIC Design Engineer",
        "FPGA Engineer",
        "RTL Design Engineer",
        "Analog IC Design Engineer",
        "Manufacturing Engineer",
        "Design Verification Engineer",
    ],
)
def test_sales_and_hardware_roles_are_hidden_by_default(title):
    assert not allowed(Job(title=title), DEFAULT)


def test_hardware_reopens_only_when_named():
    assert not allowed(Job(title="Mechanical Engineer, Robotics"), Preferences(include_titles=["engineer"]))
    assert allowed(
        Job(title="Mechanical Engineer, Robotics"), Preferences(include_titles=["mechanical engineer"])
    )
    assert allowed(Job(title="Senior Solutions Architect"), Preferences(include_presales=True))


@pytest.mark.parametrize(
    "bullet, years",
    [
        ("Work on our 10 years old codebase", None),
        ("We've grown for 15 years, join us", None),
        ("5+ years of Python", 5),
        ("3 years in backend development", 3),
        ("2+ years building APIs", 2),
        ("7 years experience with Go", 7),
        ("Minimum of 4 years professional software development", 4),
        ("3-5 years", 3),
        ("2 yrs exp", 2),
        ("Bachelor's degree and 2 years of experience", 2),
        ("1 year of university coursework in CS", None),
    ],
)
def test_job_years_are_experience_asks_only(bullet, years):
    assert years_required([bullet]) == years


@pytest.mark.parametrize(
    "text, years",
    [
        ("Software engineer with 3 years of experience", 3),
        ("Mentored engineers with 15 years of experience", None),
        ("Worked alongside staff with 20 years experience", None),
        ("3+ years of experience building APIs. Led a team with 10 years of combined experience", 3),
    ],
)
def test_resume_years_are_the_writers_own(text, years):
    assert years_from_resume(text) == years


def test_lab_and_biology_scientists_are_hidden_unless_asked_for():
    assert not title_ok("Bioinformatics Scientist – HIV-SOMAL", [], [], False)
    assert not title_ok("Senior Clinical Scientist", [], [], False)
    assert title_ok("Data Scientist", [], [], False)
    assert title_ok("Research Scientist, Machine Learning", [], [], False)
    assert title_ok("Bioinformatics Scientist", ["bioinformatics"], [], False)
