from app.ingest.run_ingest import load_slugs


def test_load_slugs_skips_comments_blanks_and_duplicates():
    text = """
# big tech
stripe
  Reddit   # inline comment

stripe
"""
    assert load_slugs(text) == ["stripe", "reddit"]


def test_other_sources_keep_their_slug_case_and_prefix():
    assert load_slugs("Ashby:OpenAI\nlever: spotify # x\nStripe\n") == ["ashby:OpenAI", "lever:spotify", "stripe"]


def test_keys_split_by_source():
    import pytest
    from app.ingest.boards_ingest import by_source
    groups = {src.name: slugs for src, slugs in by_source(["stripe", "ashby:ramp", "lever:spotify", "figma"]).items()}
    assert groups == {"greenhouse": ["stripe", "figma"], "ashby": ["ramp"], "lever": ["spotify"]}
    with pytest.raises(ValueError):
        by_source(["workday:acme"])
