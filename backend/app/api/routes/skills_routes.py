from fastapi import APIRouter

from app.services.skills_services import default_tagger

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
def list_skills() -> list[dict]:
    """Known skills with aliases, straight from skills.txt: autocomplete and "unknown skill" warnings."""
    t = default_tagger()
    names: dict[str, set[str]] = {}
    for alias, name in [*t.folded.items(), *t.exact.items()]:
        names.setdefault(name, set()).add(alias)
    return [{"name": n, "aliases": sorted(a - {n, n.lower()})} for n, a in sorted(names.items())]
