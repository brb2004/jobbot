"""Years of experience from resume text. Deterministic: stated claims first, then work-date ranges."""
import re
from datetime import date

STATED = [
    re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs)\s+(?:of\s+)?(?:professional\s+|industry\s+|work\s+|hands-on\s+)?experience", re.I),
    re.compile(r"\bwith\s+(\d{1,2})\s*\+?\s*(?:years?|yrs)\b", re.I),
]
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
MON = r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?"
RANGE = re.compile(rf"{MON}((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*{MON}((?:19|20)\d{{2}}|present|current|now)", re.I)
EXPERIENCE_HEADING = re.compile(r"^\s*(?:work\s+|professional\s+)?(?:experience|employment|work history)\s*:?\s*$", re.I)
OTHER_HEADING = re.compile(r"^\s*(?:education|skills|projects|certifications?|summary|awards|publications|volunteer\w*|interests)\b.*$", re.I)


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


def _month(name: str | None, default: int) -> int:
    return MONTHS.index(name[:3].lower()) + 1 if name else default


def years_from_resume(text: str | None, today: date | None = None) -> int | None:
    text = text or ""
    stated = [int(m.group(1)) for p in STATED for m in p.finditer(text)]
    if stated:
        return max(stated)                                        # the person's own claim
    section = _experience_section(text)
    if not section:
        return None                                               # no Experience heading: don't guess from education dates
    today = today or date.today()
    spans = []
    for m in RANGE.finditer(section):
        m1, y1, m2, y2 = m.groups()
        start = int(y1) * 12 + _month(m1, 1) - 1
        end = (today.year * 12 + today.month - 1) if y2.lower() in ("present", "current", "now") \
            else int(y2) * 12 + _month(m2, 1) - 1
        if end > start:
            spans.append((start, end))
    if not spans:
        return None
    spans.sort()
    total, (cur_s, cur_e) = 0, spans[0]
    for s, e in spans[1:]:                                        # merge overlapping jobs: count each month once
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return total // 12
