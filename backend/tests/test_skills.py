from app.services.skills_services import Tagger, default_tagger

SAMPLE = """
# label: aliases      (= means case-sensitive)
PostgreSQL: postgres, psql
Kubernetes: k8s
Java
JavaScript: js
=Go: golang
React: react.js, reactjs
React Native
C++: cpp
C#: csharp      # comments need a space before '#', so C# survives
Node.js: nodejs, =Node
"""


def test_aliases_map_to_one_display_name():
    assert Tagger.from_text(SAMPLE).tag("Postgres and k8s experience") == {"PostgreSQL", "Kubernetes"}


def test_word_boundaries_and_symbols():
    t = Tagger.from_text(SAMPLE)
    assert t.tag("JavaScript and C++, C# or Node.js") == {"JavaScript", "C++", "C#", "Node.js"}


def test_case_sensitive_names():
    t = Tagger.from_text(SAMPLE)
    assert t.tag("Go, Python") == {"Go"}
    assert t.tag("willing to go above and beyond") == set()
    assert t.tag("golang services") == {"Go"}


def test_longest_match_wins():
    assert Tagger.from_text(SAMPLE).tag("React Native apps") == {"React Native"}


def test_real_taxonomy_tags_a_real_bullet():
    bullet = "3+ years with Go, Postgres, and Kubernetes; REST or gRPC APIs on AWS"
    assert default_tagger().tag(bullet) == {"Go", "PostgreSQL", "Kubernetes", "REST", "gRPC", "AWS"}
