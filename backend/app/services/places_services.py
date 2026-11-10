"""Place names -> canonical places. Reuses the skills Tagger: same file format, whole-word and
longest-match rules, and implications ("Plano" -> Dallas-Fort Worth -> United States -> North America)."""
from functools import lru_cache
from pathlib import Path

from app.services.skills_services import Tagger

PLACES_FILE = Path(__file__).resolve().parents[2] / "places.txt"       # next to skills.txt


@lru_cache(maxsize=1)
def places() -> Tagger:
    return Tagger.from_text(PLACES_FILE.read_text())


@lru_cache(maxsize=65536)
def places_in(text: str) -> frozenset[str]:
    """Every place a posting's location names, plus everything that contains them. Cached per string:
    ~10k jobs share far fewer distinct location strings."""
    t = places()
    return frozenset(t.expand(t.tag(text)))


@lru_cache(maxsize=4096)
def place_of(entry: str) -> str | None:
    """A user's entry -> one canonical place (not expanded: "dallas" means DFW, not all of the US)."""
    found = places().tag(entry)
    return next(iter(found)) if len(found) == 1 else None
