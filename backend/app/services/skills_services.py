import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_FILE = Path(__file__).resolve().parents[2] / "skills.txt"   # backend/skills.txt
COMMENT = re.compile(r"(^|\s)#.*")                                  # '#' after a space = comment; 'C#' is not


@dataclass(frozen=True)
class Alias:
    text: str
    skill: str
    case_sensitive: bool


def parse_taxonomy(text: str) -> list[Alias]:
    """'PostgreSQL: postgres, psql' -> label + aliases. Leading '=' means match case-sensitively."""
    aliases: list[Alias] = []
    for line in text.splitlines():
        line = COMMENT.sub("", line).strip()
        if not line:
            continue
        label, _, rest = line.partition(":")
        skill = label.strip().lstrip("=")
        for raw in [label, *rest.split(",")]:
            raw = raw.strip()
            if raw:
                aliases.append(Alias(raw.lstrip("="), skill, raw.startswith("=")))
    return aliases


class Tagger:
    def __init__(self, aliases: list[Alias]):
        self.exact = {a.text: a.skill for a in aliases if a.case_sensitive}
        self.folded = {a.text.lower(): a.skill for a in aliases if not a.case_sensitive}
        ordered = sorted(aliases, key=lambda a: len(a.text), reverse=True)    # longest match wins
        parts = [re.escape(a.text) if a.case_sensitive else f"(?i:{re.escape(a.text)})" for a in ordered]
        self.pattern = re.compile(rf"(?<!\w)(?:{'|'.join(parts)})(?!\w)")    # whole words only

    @classmethod
    def from_text(cls, text: str) -> "Tagger":
        return cls(parse_taxonomy(text))

    def tag(self, text: str) -> set[str]:
        return {self.exact.get(m.group()) or self.folded[m.group().lower()]
                for m in self.pattern.finditer(text or "")}


@lru_cache
def default_tagger() -> Tagger:
    return Tagger.from_text(SKILLS_FILE.read_text())
