import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_FILE = Path(__file__).resolve().parents[2] / "skills.txt"
COMMENT = re.compile(r"(^|\s)#.*")


@dataclass(frozen=True)
class Alias:
    text: str
    skill: str
    case_sensitive: bool


def _lines(text: str):
    for line in text.splitlines():
        line = COMMENT.sub("", line).strip()
        if line:
            yield line


def parse_taxonomy(text: str) -> list[Alias]:
    aliases: list[Alias] = []
    for line in _lines(text):
        if ">" in line:
            continue
        label, _, rest = line.partition(":")
        skill = label.strip().lstrip("=")
        for raw in [label, *rest.split(",")]:
            raw = raw.strip()
            if raw:
                aliases.append(Alias(raw.lstrip("="), skill, raw.startswith("=")))
    return aliases


def parse_implications(text: str) -> dict[str, set[str]]:
    implies: dict[str, set[str]] = {}
    for line in _lines(text):
        if ">" in line:
            left, _, right = line.partition(">")
            implies.setdefault(left.strip(), set()).update(r.strip() for r in right.split(",") if r.strip())
    return implies


class Tagger:
    def __init__(self, aliases: list[Alias], implies: dict[str, set[str]] | None = None, version: str = ""):
        self.version = version
        self.implies = implies or {}
        known = {a.skill for a in aliases}
        unknown = {x for k, vs in self.implies.items() for x in (k, *vs)} - known
        if unknown:
            raise ValueError(f"implications name unknown skills: {sorted(unknown)}")
        self.exact = {a.text: a.skill for a in aliases if a.case_sensitive}
        self.folded = {a.text.lower(): a.skill for a in aliases if not a.case_sensitive}
        ordered = sorted(aliases, key=lambda a: len(a.text), reverse=True)
        parts = [re.escape(a.text) if a.case_sensitive else f"(?i:{re.escape(a.text)})" for a in ordered]
        self.pattern = re.compile(rf"(?<!\w)(?:{'|'.join(parts)})(?!\w)")

    @classmethod
    def from_text(cls, text: str) -> "Tagger":
        return cls(
            parse_taxonomy(text),
            parse_implications(text),
            version=hashlib.sha256(text.encode()).hexdigest()[:12],
        )

    def tag(self, text: str) -> set[str]:
        return {
            self.exact.get(m.group()) or self.folded[m.group().lower()]
            for m in self.pattern.finditer(text or "")
        }

    def expand(self, skills: set[str]) -> set[str]:
        out, stack = set(skills), list(skills)
        while stack:
            for implied in self.implies.get(stack.pop(), ()):
                if implied not in out:
                    out.add(implied)
                    stack.append(implied)
        return out


@lru_cache
def default_tagger() -> Tagger:
    return Tagger.from_text(SKILLS_FILE.read_text())
