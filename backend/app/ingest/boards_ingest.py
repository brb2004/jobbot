from pathlib import Path

from app.ingest.ashby_ingest import ASHBY
from app.ingest.crawl_ingest import Source
from app.ingest.greenhouse_ingest import GREENHOUSE
from app.ingest.lever_ingest import LEVER

BOARDS_FILE = Path(__file__).resolve().parents[2] / "boards.txt"
HEADERS = {"User-Agent": "jobbot3-crawler (github.com/brb2004)"}
SOURCES = (GREENHOUSE, ASHBY, LEVER)


def load_slugs(text: str) -> list[str]:
    slugs: list[str] = []
    for line in text.splitlines():
        slug = line.split("#", 1)[0].strip()
        prefix, sep, rest = slug.partition(":")
        slug = f"{prefix.lower()}:{rest.strip()}" if sep else slug.lower()
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def by_source(keys: list[str]) -> dict[Source, list[str]]:
    out: dict[Source, list[str]] = {src: [] for src in SOURCES}
    for key in keys:
        src = next((s for s in SOURCES if s.prefix and key.startswith(s.prefix)), None)
        if src is None:
            if ":" in key:
                raise ValueError(
                    f"unknown job source in {key!r} (known: ashby:, lever:, or a plain Greenhouse slug)"
                )
            src = GREENHOUSE
        out[src].append(key[len(src.prefix) :])
    return out
