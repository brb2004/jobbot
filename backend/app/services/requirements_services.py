import re

YEARS = re.compile(r"(?<!\d)(\d{1,2})\s*\+?\s*(?:(?:-|–|—|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs)\b", re.I)
EDUCATION = re.compile(
    r"\b(?:degree|universit|college|education|graduat|coursework|enrolled|student|school|"
    r"bachelor|master'?s|ph\.?d|semester)",
    re.I,
)
EXPERIENCE_WORDS = re.compile(r"\b(?:experience|experienced|exp|background|track record)\b", re.I)
LEADS_IN = re.compile(
    r"\s*(?:\)\s*)?(?:of|in|working|building|developing|writing|designing|leading|managing|shipping|"
    r"programming|coding|professional|industry|hands-on|relevant|related|or\s+more|plus)\b",
    re.I,
)

CLEARANCE = re.compile(
    r"(?<!\w)(?:clearance|u\.?\s?s\.?\s+citizen(?:ship)?|public trust|itar|ts/sci)(?!\w)", re.I
)
GOV_TITLE = re.compile(r"(?<!\w)(?:government|federal|public sector)(?!\w)", re.I)

ROLE = r"(?<!\w)(?:engineer|developer|swe|sde)\s*[-,]?\s*"
TITLE_YEARS = [
    (re.compile(r"(?<!\w)(principal|distinguished)(?!\w)", re.I), 10),
    (re.compile(r"(?<!\w)staff(?!\w)", re.I), 8),
    (re.compile(r"(?<!\w)(senior|sr\.?|lead)(?!\w)", re.I), 5),
    (re.compile(r"(?<!\w)architect(?!\w)", re.I), 5),
    (re.compile(ROLE + r"(?:iv|4)(?!\w)", re.I), 6),
    (re.compile(ROLE + r"(?:iii|3)(?!\w)", re.I), 4),
    (re.compile(ROLE + r"(?:ii|2)(?!\w)", re.I), 2),
]


def years_required(bullets: list[str]) -> int | None:
    asks = [n for b in bullets for clause in re.split(r"[;,]|\.\s", b) for n in _asks(clause)]
    return max(asks) if asks else None


def _asks(clause: str) -> list[int]:
    if EDUCATION.search(clause) and "experience" not in clause.lower():
        return []
    bare = len(re.findall(r"[a-z]{2,}", YEARS.sub("", clause), re.I)) <= 2
    about_work = bare or EXPERIENCE_WORDS.search(clause) is not None
    return [int(m.group(1)) for m in YEARS.finditer(clause) if about_work or LEADS_IN.match(clause, m.end())]


def years_from_title(title: str | None) -> int | None:
    return next((n for pattern, n in TITLE_YEARS if pattern.search(title or "")), None)


LEVEL_WORDS = r"(?:experienced|seasoned|senior|sr\.|staff|principal|lead)"
PITCH = re.compile(
    r"(?:looking for|seeking|hiring|searching for)\s+(?:an?\s+)?"
    rf"((?:{LEVEL_WORDS}[\s/,]+(?:or\s+|and\s+)?)+)[^.\n]{{0,120}}",
    re.I,
)
EXPERIENCED_YEARS = 3


def seniority_pitch(text: str | None) -> str | None:
    m = PITCH.search(text or "")
    return m.group(0) if m else None


def years_from_pitch(bullets: list[str]) -> int | None:
    found = next((m for b in bullets if (m := PITCH.search(b))), None)
    if not found:
        return None
    words = re.findall(LEVEL_WORDS, found.group(1), re.I)
    titled = [y for w in words if (y := years_from_title(w)) is not None]
    return min(titled) if titled else EXPERIENCED_YEARS


def years_note(detail: dict) -> str | None:
    y = detail.get("years_asked")
    if y is None:
        return None
    level = "senior" if y >= 5 else "mid"
    if detail.get("years_source") == "title":
        return f"{level}-level title (~{y}+ years)"
    if detail.get("years_source") == "pitch":
        return f"{level}-level role (~{y}+ years)"
    if detail.get("years_source") == "pay":
        return f"pay suggests ~{y}+ years"
    return f"asks for {y}+ years"


def needs_clearance(title: str | None, bullets: list[str]) -> bool:
    return bool(GOV_TITLE.search(title or "")) or any(CLEARANCE.search(b) for b in bullets)
