# tests/test_sections.py
from pathlib import Path
from app.ingest.sections_ingest import requirement_bullets

FIXTURES = Path(__file__).parent / "fixtures"


def test_stripe_style_strong_heading_with_nbsp():
    html = ("<p><strong>What you’ll do</strong></p><ul><li>Ship features</li></ul>"
            "<p><strong>Minimum Requirements&nbsp;</strong></p><ul><li>5+ years Go</li><li>SQL</li></ul>")
    assert requirement_bullets(html) == ["5+ years Go", "SQL"]


def test_discord_wording():
    html = ("<p><strong>What you should have</strong></p><ul><li>Python</li></ul>"
            "<p><strong>Why Discord?&nbsp;</strong></p><ul><li>Free snacks</li></ul>")
    assert requirement_bullets(html) == ["Python"]          # stops at the next heading


def test_airbnb_wording_with_colon():
    html = "<p><strong>Your Expertise:</strong></p><ul><li>Kubernetes</li></ul>"
    assert requirement_bullets(html) == ["Kubernetes"]


def test_bold_words_inside_a_bullet_are_not_headings():
    html = ("<p><strong>Requirements</strong></p>"
            "<ul><li><strong>Strong</strong> Go skills</li><li>Docker</li></ul>")
    assert requirement_bullets(html) == ["Strong Go skills", "Docker"]


def test_real_postings_all_yield_bullets():
    for name in ("stripe", "discord", "airbnb", "databricks", "lyft", "robinhood", "asana", "databricks_2"):
        bullets = requirement_bullets((FIXTURES / f"{name}.html").read_text())
        assert bullets, f"{name}: found no requirement bullets"

def test_inline_bold_and_empty_strong_do_not_end_the_section():
    html = ("<p><strong>Your Expertise:</strong></p><p>You <strong>must</strong> know:</p>"
            "<p><strong>&nbsp;</strong></p><ul><li>Go</li></ul>")
    assert requirement_bullets(html) == ["Go"]


def test_inline_bold_and_empty_strong_do_not_end_the_section():
    html = ("<p><strong>Your Expertise:</strong></p><p>You <strong>must</strong> know:</p>"
            "<p><strong>&nbsp;</strong></p><ul><li>Go</li></ul>")
    assert requirement_bullets(html) == ["Go"]


def test_plain_paragraph_heading_with_colon():
    html = ("<p>The impact you will have:</p><ul><li>Lead projects</li></ul>"
            "<p>What we look for:</p><ul><li>6+ years data engineering</li></ul>"
            "<p><strong>Benefits</strong></p><ul><li>Equity</li></ul>")
    assert requirement_bullets(html) == ["6+ years data engineering"]


def test_long_paragraph_ending_in_colon_is_not_a_heading():
    html = ("<p><strong>Requirements</strong></p>"
            "<p>Below is a fairly long sentence introducing the list of things we need:</p>"
            "<ul><li>Go</li></ul>")
    assert requirement_bullets(html) == ["Go"]
