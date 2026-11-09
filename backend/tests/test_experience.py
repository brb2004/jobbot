from datetime import date

from app.services.experience_services import years_from_resume

TODAY = date(2026, 11, 1)


def test_stated_years_win():
    assert years_from_resume("Backend engineer with 2 years building APIs.", TODAY) == 2
    assert years_from_resume("5+ years of professional experience in Python", TODAY) == 5


def test_date_ranges_in_the_experience_section_are_merged_and_summed():
    text = """Alex Rivera
Experience
Acme, Software Engineer
Jan 2022 – Mar 2024
Beta, Platform Engineer
2024 – Present
Education
B.S. Computer Science, 2018 – 2022
"""
    # 2022-01..2024-03 overlaps 2024-01..2026-11 -> one stretch 2022-01..2026-11 = 58 months = 4 years.
    # The degree's 2018-2022 is in Education, so it doesn't count.
    assert years_from_resume(text, TODAY) == 4


def test_no_evidence_means_unknown():
    assert years_from_resume("Python, Go, Docker. B.S. Computer Science, 2018 – 2022", TODAY) is None
