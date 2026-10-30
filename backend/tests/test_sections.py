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
    for name in ("stripe", "discord", "airbnb", "databricks"):
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
