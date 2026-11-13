from app.services.scoring_services import years_from_title, years_note


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
    from app.services.scoring_services import years_from_title

    assert years_from_title("AI Architect") == 5
    assert years_from_title("Solutions Architect (FedS062)") == 5
    assert years_from_title("Principal Architect") == 10  # the stronger word wins
    assert years_from_title("Software Engineer, Architecture Tooling") is None
