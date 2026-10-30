import re

from selectolax.lexbor import LexborHTMLParser

HEADINGS = "strong, h1, h2, h3, h4, h5, h6"
REQUIREMENT_HEADING = re.compile(
    r"requirement|qualification|should have|you have|who you are|expertise|you.ll bring|skills|look(ing)? for",
    re.IGNORECASE,
)


def clean(text: str) -> str:
    return text.replace("\xa0", " ").strip().rstrip(":").strip()


def is_heading(node) -> bool:
    """Real h1-h6 always; <strong> only when it's the whole text of its parent (not bold inside a sentence or bullet)."""
    if node.tag != "strong":
        return True
    parent = node.parent
    return parent is not None and clean(parent.text(deep=True)) == clean(node.text(deep=True))


def requirement_bullets(html: str) -> list[str]:
    tree = LexborHTMLParser(html)
    in_requirements = False
    bullets: list[str] = []
    for node in tree.css(f"{HEADINGS}, li"):                    # document order
        if node.tag == "li":
            text = clean(node.text(deep=True))
            if in_requirements and text:
                bullets.append(text)
            continue
        title = clean(node.text(deep=True))
        if not title or not is_heading(node):                  # empty or inline bold: ignore, keep state
            continue
        in_requirements = bool(REQUIREMENT_HEADING.search(title))
    return bullets
