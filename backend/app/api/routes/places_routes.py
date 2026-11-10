from functools import lru_cache

from fastapi import APIRouter

from app.services.places_services import PLACES_FILE, places

router = APIRouter(prefix="/places", tags=["places"])
MARKERS = {"[metro]": "metro", "[country]": "country", "[region]": "region"}


@lru_cache(maxsize=1)
def _sections() -> tuple[dict[str, str], dict[str, str]]:
    """places.txt markers: "# [country]" sets the kind of the places that follow; "# [labels]" holds
    "# Name = Display label" lines."""
    kinds, labels, current = {}, {}, None
    for line in PLACES_FILE.read_text().splitlines():
        s = line.strip()
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            if body.startswith("[labels]"):
                current = "labels"
            elif body in MARKERS:
                current = MARKERS[body]
            elif current == "labels" and " = " in body:
                name, label = body.split(" = ", 1)
                labels[name.strip()] = label.strip()
            continue
        if s and ">" not in s and current in MARKERS.values():
            kinds[s.split(":", 1)[0].strip().lstrip("=")] = current
    return kinds, labels


@router.get("")
def list_places() -> list[dict]:
    """Canonical places with kind and aliases, straight from places.txt: the pickers agree with matching."""
    t = places()
    names: dict[str, set[str]] = {}
    for alias, name in [*t.folded.items(), *t.exact.items()]:
        names.setdefault(name, set()).add(alias)
    kinds, labels = _sections()
    return [{"name": n, "label": labels.get(n, n), "kind": kinds.get(n), "aliases": sorted(a - {n.lower()})}
            for n, a in sorted(names.items())]
