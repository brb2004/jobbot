import re
from functools import lru_cache

from app.core.words_core import has_any
from app.services.places_services import PLACES_FILE, place_of, places, places_in, places_named

REMOTE = ("remote", "distributed")
BLOCKED_PLACES = ("tel aviv",)


def _pieces(location: str | None) -> list[str]:
    pieces = [p.strip() for p in re.split(r"[;|•]", location or "") if p.strip()]
    places = [p for p in pieces if not _bare_remote(p)]
    if places and len(places) < len(pieces):
        return [f"{p} (remote)" if not has_any(p, REMOTE) else p for p in places]
    return pieces


def _bare_remote(piece: str) -> bool:
    return not re.sub(r"(?i)remote|distributed|[\W_]", "", piece)


def location_blocked(location: str | None) -> bool:
    pieces = _pieces(location)
    return bool(pieces) and all(has_any(p, BLOCKED_PLACES) for p in pieces)


@lru_cache(maxsize=4096)
def _wants(entries: tuple[str, ...]) -> tuple[frozenset[str], tuple[str, ...]]:
    ids = frozenset(p for e in entries if (p := place_of(e)))
    words = tuple(e for e in entries if not place_of(e))
    return ids, words + (("distributed",) if "remote" in words else ())


@lru_cache(maxsize=1)
def _regions() -> frozenset[str]:
    names, inside = set(), False
    for line in PLACES_FILE.read_text().splitlines():
        if line.startswith("# ["):
            inside = line.startswith("# [region]")
        elif inside and line.strip() and not line.startswith("#"):
            names.add(line.split(":")[0].strip())
    return frozenset(names)


@lru_cache(maxsize=4096)
def _up(ids: frozenset[str]) -> frozenset[str]:
    return frozenset(places().expand(set(ids)))


def _abroad(pieces: list[str], ids: frozenset[str]) -> bool:
    home = _up(ids) - _regions()
    named = frozenset().union(*(places_named(p) for p in pieces)) - _regions()
    return bool(home and named) and not any(places_in(n) & home for n in named)


@lru_cache(maxsize=4096)
def _around(ids: frozenset[str]) -> frozenset[str]:
    return frozenset().union(*(places_in(i) for i in ids)) if ids else frozenset()


def location_ok(location: str | None, prefs) -> bool:
    want_ids, want_words = _wants(tuple(prefs.locations))
    anywhere = not want_ids and not want_words
    pieces = _pieces(location)
    if not pieces:
        return anywhere
    if _abroad(pieces, want_ids):
        return False
    return any(_piece_ok(p, prefs, want_ids, want_words, anywhere) for p in pieces)


def _piece_ok(piece: str, prefs, want_ids, want_words, anywhere: bool) -> bool:
    if has_any(piece, BLOCKED_PLACES):
        return False
    remote = has_any(piece, REMOTE)
    if not (prefs.remote if remote else prefs.onsite):
        return False
    if anywhere or places_in(piece) & want_ids or has_any(piece, want_words):
        return True
    return remote and (_bare_remote(piece) or bool(places_named(piece) & _around(want_ids)))
