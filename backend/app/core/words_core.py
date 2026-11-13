"""Whole-word phrase matching, one cached regex per word list."""

import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def _pattern(words: tuple[str, ...], hyphen_joins: bool) -> re.Pattern:
    edge = r"[\w-]" if hyphen_joins else r"\w"  # hyphen_joins: "go" doesn't match inside "Go-to-Market"
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!{edge})(?:{alts})(?!{edge})", re.IGNORECASE)


def has_any(text: str, words, hyphen_joins: bool = False) -> bool:
    return bool(words) and _pattern(tuple(words), hyphen_joins).search(text) is not None


def has_word(text: str, word: str) -> bool:
    return has_any(text, (word,))
