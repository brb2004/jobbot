import re

from selectolax.lexbor import LexborHTMLParser

HEADINGS = "strong, h1, h2, h3, h4, h5, h6, p"
REQUIREMENT_HEADING = re.compile(
    r"requirement|qualification|should have|you have|who you are|expertise|you(.ll)? bring|skills"
    r"|look(ing)? for|^experience|^preferred|about you|you need|^bonus",
    re.IGNORECASE,
)

BOILERPLATE = re.compile(
    r"equal opportunity|accommodation|e-verify|arbitration|privacy notice|application limit"
    r"|know your rights|protected veteran",
    re.IGNORECASE,
)


def text_of(node) -> str:
    # separator=" ": "<span>field</span><span>of</span>" -> "field of", not "fieldof"
    return node.text(deep=True, separator=" ")


def clean(text: str) -> str:
    text = " ".join(text.replace("\xa0", " ").split())  # collapse runs of whitespace
    text = re.sub(r" ([,.;:!?)])", r"\1", text)  # "Go ," -> "Go,"
    text = text.replace("( ", "(")
    return text.rstrip(":").strip()


def is_heading(node) -> bool:
    if node.tag == "p":
        raw = text_of(node).strip()
        plain = next(node.iter(include_text=False), None) is None
        return plain and raw.endswith(":") and len(raw) <= 40
    if node.tag != "strong":
        return True
    parent = node.parent
    return parent is not None and clean(text_of(parent)) == clean(text_of(node))


def requirement_bullets(html: str) -> list[str]:
    tree = LexborHTMLParser(html)
    in_requirements = False
    bullets: list[str] = []
    for node in tree.css(f"{HEADINGS}, li"):  # document order
        if node.tag == "li":
            text = clean(text_of(node))
            if in_requirements and text and not BOILERPLATE.search(text):
                bullets.append(text)
            continue
        title = clean(text_of(node))
        if not title or not is_heading(node):
            continue
        in_requirements = bool(REQUIREMENT_HEADING.search(title))
    return bullets
