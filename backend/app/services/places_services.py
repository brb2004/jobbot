"""Place names -> canonical places. Reuses the skills Tagger: same file format, whole-word and
longest-match rules, and implications ("Plano" -> Dallas-Fort Worth -> United States -> North America)."""

import re
from functools import lru_cache
from pathlib import Path

from app.services.skills_services import Tagger

PLACES_FILE = Path(__file__).resolve().parents[2] / "places.txt"  # next to skills.txt


def _flat(text: str) -> str:
    """Commas don't matter in place names: "Vancouver, WA" reads as "Vancouver WA" (names can't hold commas)."""
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
    """Metro -> its state or province, from the labels block ("# Dallas-Fort Worth = Dallas-Fort Worth, TX")."""
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
    """Tag, then drop cities the text puts in another state: "Arlington, VA" is not Arlington, TX (DFW).
    Kept when no state is given, or when one of the states given is the city's own ("Dallas, TX / Arlington, VA")."""
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
    """Every place a posting's location names, plus everything that contains them. Cached per string:
    ~10k jobs share far fewer distinct location strings."""
    t = places()
    return frozenset(t.expand(_tag(text)))


@lru_cache(maxsize=4096)
def place_of(entry: str) -> str | None:
    """A user's entry -> one canonical place (not expanded: "dallas" means DFW, not all of the US)."""
    found = _tag(entry)
    return next(iter(found)) if len(found) == 1 else None


@lru_cache(maxsize=65536)
def places_named(text: str) -> frozenset[str]:
    """Only the places a text names, not what contains them: "Remote - Mexico" -> {Mexico}, never North America."""
    return frozenset(_tag(text))
