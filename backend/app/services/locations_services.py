"""Does a job's location fit the places a user picked and their on-site / remote choice?"""

import re
from functools import lru_cache

from app.core.words_core import has_any
from app.services.places_services import place_of, places_in, places_named

REMOTE = ("remote", "distributed")
# Product decision: places JobMatch doesn't list. A job only located there is never shown, and a
# blocked place is never the reason a job matches.
BLOCKED_PLACES = ("tel aviv",)


def _pieces(location: str | None) -> list[str]:
    """ "SF, CA; Remote, US" is two locations."""
    return [p.strip() for p in re.split(r"[;|•]", location or "") if p.strip()]


def location_blocked(location: str | None) -> bool:
    pieces = _pieces(location)
    return bool(pieces) and all(has_any(p, BLOCKED_PLACES) for p in pieces)


@lru_cache(maxsize=4096)
def _wants(entries: tuple[str, ...]) -> tuple[frozenset[str], tuple[str, ...]]:
    """User entries -> (known places, leftover words matched as plain words)."""
    ids = frozenset(p for e in entries if (p := place_of(e)))
    words = tuple(e for e in entries if not place_of(e))
    return ids, words + (("distributed",) if "remote" in words else ())


@lru_cache(maxsize=4096)
def _around(ids: frozenset[str]) -> frozenset[str]:
    """Your places plus everything containing them: Dallas-Fort Worth -> United States -> North America."""
    return frozenset().union(*(places_in(i) for i in ids)) if ids else frozenset()


def location_ok(location: str | None, prefs) -> bool:
    """On-site and hybrid: inside a place you picked. Remote: open to where you are ("Remote - US" fits
    Dallas-Fort Worth, "Remote - Mexico" doesn't, plain "Remote" fits everyone). No places = anywhere."""
    want_ids, want_words = _wants(tuple(prefs.locations))
    anywhere = not want_ids and not want_words
    pieces = _pieces(location)
    if not pieces:
        return anywhere
    return any(_piece_ok(p, prefs, want_ids, want_words, anywhere) for p in pieces)


def _piece_ok(piece: str, prefs, want_ids, want_words, anywhere: bool) -> bool:
    if has_any(piece, BLOCKED_PLACES):
        return False
    remote = has_any(piece, REMOTE)
    if not (prefs.remote if remote else prefs.onsite):
        return False
    if anywhere or places_in(piece) & want_ids or has_any(piece, want_words):
        return True
    just_remote = not re.sub(r"(?i)remote|distributed|[\W_]", "", piece)
    return remote and (just_remote or bool(places_named(piece) & _around(want_ids)))
