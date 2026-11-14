import re

from selectolax.lexbor import LexborHTMLParser

from app.ingest.sections_ingest import HEADINGS, REQUIREMENT_HEADING, clean, is_heading, text_of

NONE, ASSOCIATE, BACHELOR, MASTER, PHD = range(5)
LEVELS = (
    (PHD, re.compile(r"(?<!\w)(?:ph\.?\s?d|doctorate|doctoral)(?!\w)", re.I)),
    (
        MASTER,
        re.compile(r"(?<!\w)(?:master'?s|msc|mba)(?!\w)|(?<!\w)m\.?s\.?(?=\s+(?:degree|in|or)\b|\s*/)", re.I),
    ),
    (
        BACHELOR,
        re.compile(
            r"(?<!\w)(?:b\.?s\.?c?|b\.?a\.?)(?=\s+(?:degree|in|or)\b|\s*/)|(?<!\w)bachelor|undergraduate degree"
            r"|(?:four|4)[- ]year degree|(?:college|university) degree|(?<!\w)degree in\b",
            re.I,
        ),
    ),
    (ASSOCIATE, re.compile(r"(?<!\w)associate'?s degree", re.I)),
)
SOFT_HEADING = re.compile(r"prefer|nice|bonus|plus|desir|ideal|great if|stand out|extra", re.I)
ESCAPE = re.compile(
    r"equivalent|in lieu|or (?:related |relevant |practical |professional |work )*experience|comparable"
    r"|prefer|nice to have|bonus|\bplus\b|desired|ideally|not required|optional|pursuing|enrolled"
    r"|expected|working toward|or \d+\+?\s*(?:years|yrs)",
    re.I,
)


def required_degree(html: str | None) -> int:
    level, hard = NONE, False
    for node in LexborHTMLParser(html or "").css(f"{HEADINGS}, li"):
        if node.tag == "li":
            level = max(level, bullet_degree(clean(text_of(node)))) if hard else level
            continue
        title = clean(text_of(node))
        if title and is_heading(node):
            hard = bool(REQUIREMENT_HEADING.search(title)) and not SOFT_HEADING.search(title)
    return level


def bullet_degree(text: str) -> int:
    if ESCAPE.search(text):
        return NONE
    found = [level for level, pattern in LEVELS if pattern.search(text)]
    return min(found) if found else NONE
