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


def has_python(t: str) -> bool:
    return "python" in t.lower()


def test_roles_without_skills_dont_count_inline_titles():
    text = """Experience
Warehouse Associate — Amazon   Coppell, TX  |  2020 – 2023
Picked and packed orders on a fast-paced floor
Python Developer — Acme   Remote  |  Jan 2023 – Present
Built Python APIs
Education
"""
    assert years_from_resume(text, TODAY) == 6                        # every role: 2020-01..2026-11
    assert years_from_resume(text, TODAY, has_skills=has_python) == 3  # warehouse skipped: 2023-01..2026-11


def test_roles_without_skills_dont_count_title_above_dates():
    text = """Experience
Amazon, Warehouse Associate
2020 – 2023
Picked and packed orders
Acme, Python Developer
Jan 2023 – Present
Built Python APIs
"""
    assert years_from_resume(text, TODAY, has_skills=has_python) == 3


def test_work_history_with_no_technical_roles_is_zero_not_unknown():
    text = "Experience\nWarehouse Associate — Amazon | 2020 – 2023\nPacked orders\n"
    assert years_from_resume(text, TODAY, has_skills=has_python) == 0
