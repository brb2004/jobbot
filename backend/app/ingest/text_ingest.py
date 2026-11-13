import html as htmllib

from selectolax.lexbor import LexborHTMLParser

BLOCK = ("p", "div", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "section")


def html_to_text(raw: str) -> str:
    if "&lt;" in raw:  # Greenhouse double-encodes
        raw = htmllib.unescape(raw)
    tree = LexborHTMLParser(raw)
    for node in tree.css("script, style, noscript"):
        node.decompose()
    for node in tree.css("br"):
        node.replace_with("\n")
    for node in tree.css("li"):
        node.insert_before("\n• ")
    for node in tree.css(", ".join(BLOCK)):
        node.insert_before("\n")
        node.insert_after("\n")
    root = tree.body or tree.root
    return tidy(root.text(deep=True) if root else "")


def tidy(raw: str) -> str:
    out, blank = [], 0
    for line in raw.splitlines():
        line = " ".join(line.split())
        if not line:
            blank += 1
            if blank == 1 and out:
                out.append("")
        else:
            blank = 0
            out.append(line)
    return "\n".join(out).strip()
