import re
from functools import lru_cache
from pathlib import Path

from app.services.skills_services import Tagger

PLACES_FILE = Path(__file__).resolve().parents[2] / "places.txt"  # next to skills.txt


def _flat(text: str) -> str:
    return re.sub(r"[\s,]+", " ", text).strip()


@lru_cache(maxsize=1)
def places() -> Tagger:
    return Tagger.from_text(PLACES_FILE.read_text())


US_STATES = {
    "AL": "alabama",
    "AK": "alaska",
    "AZ": "arizona",
    "AR": "arkansas",
    "CA": "california",
    "CO": "colorado",
    "CT": "connecticut",
    "DE": "delaware",
    "DC": "district of columbia",
    "FL": "florida",
    "GA": "georgia",
    "HI": "hawaii",
    "ID": "idaho",
    "IL": "illinois",
    "IN": "indiana",
    "IA": "iowa",
    "KS": "kansas",
    "KY": "kentucky",
    "LA": "louisiana",
    "ME": "maine",
    "MD": "maryland",
    "MA": "massachusetts",
    "MI": "michigan",
    "MN": "minnesota",
    "MS": "mississippi",
    "MO": "missouri",
    "MT": "montana",
    "NE": "nebraska",
    "NV": "nevada",
    "NH": "new hampshire",
    "NJ": "new jersey",
    "NM": "new mexico",
    "NY": "new york",
    "NC": "north carolina",
    "ND": "north dakota",
    "OH": "ohio",
    "OK": "oklahoma",
    "OR": "oregon",
    "PA": "pennsylvania",
    "RI": "rhode island",
    "SC": "south carolina",
    "SD": "south dakota",
    "TN": "tennessee",
    "TX": "texas",
    "UT": "utah",
    "VT": "vermont",
    "VA": "virginia",
    "WA": "washington",
    "WV": "west virginia",
    "WI": "wisconsin",
    "WY": "wyoming",
}
PROVINCES = {
    "AB": "alberta",
    "BC": "british columbia",
    "MB": "manitoba",
    "NB": "new brunswick",
    "NL": "newfoundland",
    "NS": "nova scotia",
    "ON": "ontario",
    "PE": "prince edward island",
    "QC": "quebec",
    "SK": "saskatchewan",
}
_REGIONS = US_STATES | PROVINCES
_CODE = re.compile(r"\b(" + "|".join(_REGIONS) + r")\b")  # upper case only: "or" isn't Oregon
_NAME = re.compile(
    r"(?i)\b(" + "|".join(sorted(map(re.escape, _REGIONS.values()), key=len, reverse=True)) + r")\b"
)
_BY_NAME = {v: k for k, v in _REGIONS.items()}


@lru_cache(maxsize=1)
def _state_of() -> dict[str, str]:
    out, in_labels = {}, False
    for line in PLACES_FILE.read_text().splitlines():
        body = line.strip().lstrip("#").strip()
        if body.startswith("[labels]"):
            in_labels = True
        elif in_labels and " = " in body:
            name, label = body.split(" = ", 1)
            code = label.rsplit(", ", 1)[-1].strip()
            if code in _REGIONS:
                out[name.strip()] = code
    return out


def _regions_said(text: str) -> set[str]:
    return set(_CODE.findall(text)) | {_BY_NAME[n.lower()] for n in _NAME.findall(text)}


def _tag(text: str) -> set[str]:
    found = places().tag(_flat(text))
    said = _regions_said(text)
    if not said:
        return found
    state = _state_of()
    return {
        p for p in found if (s := state.get(p)) is None or s in said or (s in PROVINCES and said <= {"CA"})
    }  # "Toronto, CA": CA means Canada here


@lru_cache(maxsize=65536)
def places_in(text: str) -> frozenset[str]:
    t = places()
    return frozenset(t.expand(_tag(text)))


@lru_cache(maxsize=4096)
def place_of(entry: str) -> str | None:
    found = _tag(entry)
    return next(iter(found)) if len(found) == 1 else None


@lru_cache(maxsize=65536)
def places_named(text: str) -> frozenset[str]:
    return frozenset(_tag(text))
