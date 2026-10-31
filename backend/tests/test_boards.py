from app.ingest.run_ingest import load_slugs


def test_load_slugs_skips_comments_blanks_and_duplicates():
    text = """
# big tech
stripe
  Reddit   # inline comment

stripe
"""
    assert load_slugs(text) == ["stripe", "reddit"]
