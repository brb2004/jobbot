import re
from collections.abc import Callable
from datetime import date

STATED = [
    re.compile(
        r"(\d{1,2})\s*\+?\s*(?:years?|yrs)\s+(?:of\s+)?(?:professional\s+|industry\s+|work\s+|hands-on\s+)?experience",
        re.I,
    ),
    re.compile(r"\bwith\s+(\d{1,2})\s*\+?\s*(?:years?|yrs)\b", re.I),
]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MON = r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?"
RANGE = re.compile(
    rf"{MON}((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*{MON}((?:19|20)\d{{2}}|present|current|now)", re.I
)
EXPERIENCE_HEADING = re.compile(
    r"^\s*(?:work\s+|professional\s+)?(?:experience|employment|work history)\s*:?\s*$", re.I
)
OTHER_HEADING = re.compile(
    r"^\s*(?:education|skills|projects|certifications?|summary|awards|publications|volunteer\w*|interests)\b.*$",
    re.I,
)
WORDS = re.compile(r"[A-Za-z]{3}")


def _experience_section(text: str) -> str | None:
    lines, keep, inside = text.splitlines(), [], False
    for line in lines:
        if EXPERIENCE_HEADING.match(line):
            inside = True
            continue
        if inside and OTHER_HEADING.match(line):
            break
        if inside:
            keep.append(line)
    return "\n".join(keep) if inside else None


def _roles(section: str) -> list[tuple[re.Match, str]]:
    lines = section.splitlines()
    starts = [i for i, line in enumerate(lines) if RANGE.search(line)]
    heads = []
    for n, i in enumerate(starts):
        inline_title = WORDS.search(RANGE.sub("", lines[i]))
        prev_free = i > 0 and (n == 0 or i - 1 > starts[n - 1]) and lines[i - 1].strip()
        heads.append(i - 1 if prev_free and not inline_title else i)
    return [
        (
            RANGE.search(lines[i]),
            "\n".join(lines[heads[n] : heads[n + 1] if n + 1 < len(heads) else len(lines)]),
        )
        for n, i in enumerate(starts)
    ]


def _month(name: str | None, default: int) -> int:
    return MONTHS.index(name[:3].lower()) + 1 if name else default


def _span(m: re.Match, today: date) -> tuple[int, int]:
    m1, y1, m2, y2 = m.groups()
    start = int(y1) * 12 + _month(m1, 1) - 1
    end = (
        (today.year * 12 + today.month - 1)
        if y2.lower() in ("present", "current", "now")
        else int(y2) * 12 + _month(m2, 1) - 1
    )
    return start, end


# "mentored engineers with 15 years of experience", "a team averaging 10 years": someone else's years.
OTHERS = re.compile(
    r"\b(?:engineers|developers|team|teams|members|staff|people|clients|customers|users|"
    r"company|companies|organization|organizations|firm|colleagues|peers|mentees|interns|"
    r"students|reports|mentored|managed|supervised|led|hired|coached|alongside|averaging)\b",
    re.IGNORECASE,
)


def _own_claim(text: str, m: re.Match) -> bool:
    start = (
        max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start()), text.rfind("•", 0, m.start())) + 1
    )
    return OTHERS.search(text, start, m.start()) is None


def years_from_resume(
    text: str | None, today: date | None = None, has_skills: Callable[[str], bool] | None = None
) -> int | None:
    text = text or ""
    stated = [int(m.group(1)) for p in STATED for m in p.finditer(text) if _own_claim(text, m)]
    if stated:
        return max(stated)  # the person's own claim
    section = _experience_section(text)
    if not section:
        return None  # no Experience heading: don't guess from education dates
    today = today or date.today()
    roles = _roles(section)
    if not roles:
        return None
    spans = sorted(
        s
        for m, body in roles
        if (has_skills is None or has_skills(body)) and (s := _span(m, today))[1] > s[0]
    )
    if not spans:
        return 0  # worked, but no technical roles
    total, (cur_s, cur_e) = 0, spans[0]
    for s, e in spans[1:]:  # merge overlapping jobs: count each month once
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return total // 12
