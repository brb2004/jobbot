from functools import lru_cache

from fastapi import APIRouter

from app.services.places_services import PLACES_FILE, places

router = APIRouter(prefix="/places", tags=["places"])
MARKERS = {"[metro]": "metro", "[country]": "country", "[region]": "region"}


@lru_cache(maxsize=1)
def _kinds() -> dict[str, str]:
    """Section markers in places.txt ("# [country]") say what kind each following place is."""
    kinds, current = {}, None
    for line in PLACES_FILE.read_text().splitlines():
        s = line.strip()
        if s.startswith("#"):
            current = MARKERS.get(s.lstrip("#").strip(), current)
            continue
        if s and ">" not in s and current:
            kinds[s.split(":", 1)[0].strip().lstrip("=")] = current
    return kinds


@router.get("")
def list_places() -> list[dict]:
    """Canonical places with kind and aliases, straight from places.txt: the pickers agree with matching."""
    t = places()
    names: dict[str, set[str]] = {}
    for alias, name in [*t.folded.items(), *t.exact.items()]:
        names.setdefault(name, set()).add(alias)
    return [{"name": n, "kind": _kinds().get(n), "aliases": sorted(a - {n.lower()})} for n, a in sorted(names.items())]
