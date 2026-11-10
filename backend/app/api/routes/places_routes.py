from fastapi import APIRouter

from app.services.places_services import places

router = APIRouter(prefix="/places", tags=["places"])


@router.get("")
def list_places() -> list[dict]:
    """Canonical places with their aliases, straight from places.txt, so the pickers always agree with matching."""
    t = places()
    names: dict[str, set[str]] = {}
    for alias, name in [*t.folded.items(), *t.exact.items()]:
        names.setdefault(name, set()).add(alias)
    return [{"name": n, "aliases": sorted(a - {n.lower()})} for n, a in sorted(names.items())]
