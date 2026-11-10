import re
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, User
from app.services.places_services import place_of, places_in, places_named

Word = Annotated[str, Field(min_length=1, max_length=50)]
# Tech-only product: with no include list, show engineering roles. Users can override with their own list.
DEFAULT_TITLES = ("engineer", "developer", "sre", "devops", "architect", "programmer", "scientist")
# Sales / pre-sales roles that contain "engineer" or "architect". Hidden unless the user opts in.
PRESALES_TITLES = ("sales", "presales", "pre-sales", "customer engineer", "solutions architect",
                   "solution architect", "solutions engineer", "solution engineer", "account executive",
                   "customer success")


# Titles with "engineer"/"developer" that aren't software-building roles. Hidden unless the user lists
# one of these phrases in include titles (a generic "engineer" doesn't reopen them).
NON_DEV_TITLES = ("support engineer", "technical support", "customer support", "curriculum",
                  "creative engineer", "enterprise engineer", "help desk", "helpdesk")


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_titles: list[Word] = Field(default=[], max_length=50)   # title must contain one (empty = DEFAULT_TITLES)
    exclude_titles: list[Word] = Field(default=[], max_length=50)   # title must contain none
    locations: list[Word] = Field(default=[], max_length=50)        # a job location must contain one (if set)
    remote: bool = True                                              # show remote jobs open to your locations
    onsite: bool = True                                              # show on-site/hybrid jobs in your locations
    years_experience: int | None = Field(default=None, ge=0, le=60)  # jobs asking > this + 1 sink
    extra_skills: list[Word] = Field(default=[], max_length=50)     # skills not on the resume
    include_presales: bool = False                                   # opt in to PRESALES_TITLES

    @field_validator("include_titles", "exclude_titles", "locations", "extra_skills")
    @classmethod
    def _clean(cls, words: list[str], info) -> list[str]:
        keep_case = info.field_name == "extra_skills"          # "Go", "REST" are case-sensitive skills
        out, seen = [], set()
        for w in words:
            w = w.strip()
            if not w:
                raise ValueError("entries can't be blank")
            w = w if keep_case else w.lower()
            if w.lower() not in seen:                          # dedupe case-insensitively, keep the first
                seen.add(w.lower())
                out.append(w)
        return out

    @model_validator(mode="before")
    @classmethod
    def _legacy_locations(cls, data):
        """Old shape: "remote" as a location word plus a remote_regions list. New: places + two switches.
        Converted on read, so saved preferences keep matching the same jobs."""
        if not isinstance(data, dict):
            return data
        old = list(data.get("locations") or [])
        if "remote_regions" not in data and not any(str(l).strip().lower() == "remote" for l in old):
            return data
        data = dict(data)
        regions = data.pop("remote_regions", None) or []
        places = [l for l in old if str(l).strip().lower() != "remote"]
        wants_remote = len(places) != len(old)
        if wants_remote and not places:                 # remote-only: the regions said where
            data.update(locations=list(regions), remote=True, onsite=False)
        else:
            data.update(locations=places, remote=wants_remote or not old, onsite=True)
        return data

    @model_validator(mode="after")
    def _no_contradictions(self):
        if not (self.remote or self.onsite):
            raise ValueError("pick on-site, remote, or both")
        both = sorted(set(self.include_titles) & set(self.exclude_titles))
        if both:
            raise ValueError(f"'{both[0]}' is in both include and exclude titles")
        return self


def has_word(text: str, word: str) -> bool:
    return has_any(text, (word,))


@lru_cache(maxsize=4096)
def _any_word(words: tuple[str, ...], hyphen_joins: bool) -> re.Pattern:
    """All words -> ONE compiled pattern, cached. hyphen_joins: 'go' must not match inside 'Go-to-Market'."""
    edge = r"[\w-]" if hyphen_joins else r"\w"
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<!{edge})(?:{alts})(?!{edge})", re.IGNORECASE)


def has_any(text: str, words, hyphen_joins: bool = False) -> bool:
    return bool(words) and _any_word(tuple(words), hyphen_joins).search(text) is not None


REMOTE = ("remote", "distributed")
# Product decision: locations JobMatch doesn't list. A job whose only locations are here is never shown,
# and a blocked location is never the reason a job matches.
BLOCKED_PLACES = ("tel aviv",)


def _blocked(piece: str) -> bool:
    return has_any(piece, BLOCKED_PLACES)


def location_blocked(location: str | None) -> bool:
    pieces = [p.strip() for p in re.split(r"[;|\u2022]", location or "") if p.strip()]
    return bool(pieces) and all(_blocked(p) for p in pieces)


@lru_cache(maxsize=4096)
def _wants(entries: tuple[str, ...]) -> tuple[frozenset[str], tuple[str, ...]]:
    """User entries -> (known places, leftover words). Leftovers keep the old word matching."""
    ids, words = set(), []
    for e in entries:
        p = place_of(e)
        if p:
            ids.add(p)
        else:
            words.append(e)
    if "remote" in words:
        words.append("distributed")                         # "Distributed" postings are remote too
    return frozenset(ids), tuple(words)


@lru_cache(maxsize=4096)
def _around(ids: frozenset[str]) -> frozenset[str]:
    """Your places plus everything that contains them: Dallas-Fort Worth -> United States -> North America."""
    return frozenset().union(*(places_in(i) for i in ids)) if ids else frozenset()


def location_ok(location: str | None, prefs: Preferences) -> bool:
    """On-site/hybrid jobs: inside a place you picked. Remote jobs: open to where you are ("Remote - US" fits
    Dallas-Fort Worth; "Remote - Mexico" doesn't; plain "Remote" fits everyone). Nothing picked = anywhere."""
    want_ids, want_words = _wants(tuple(prefs.locations))
    anywhere = not want_ids and not want_words
    pieces = [p.strip() for p in re.split(r"[;|\u2022]", location or "") if p.strip()]   # "SF, CA; Remote, US" = 2
    if not pieces:
        return anywhere                                     # unknown location: only with no place filter
    near = _around(want_ids)
    for piece in pieces:
        if _blocked(piece):
            continue
        remote = has_any(piece, REMOTE)
        if (remote and not prefs.remote) or (not remote and not prefs.onsite):
            continue
        if anywhere or places_in(piece) & want_ids or has_any(piece, want_words):
            return True                                     # in (or inside) a place you picked
        bare = not re.sub(r"(?i)remote|distributed|[\W_]", "", piece)       # just "Remote"
        if remote and (bare or places_named(piece) & near):
            return True                                     # remote, open to where you are
    return False


def allowed(job: Job, prefs: Preferences) -> bool:
    if location_blocked(job.location):
        return False
    title = job.title or ""
    if has_any(title, prefs.exclude_titles, hyphen_joins=True):
        return False
    if not prefs.include_presales and has_any(title, PRESALES_TITLES, hyphen_joins=True):
        return False
    if has_any(title, NON_DEV_TITLES, hyphen_joins=True) and \
            not any(has_any(t, NON_DEV_TITLES, hyphen_joins=True) for t in prefs.include_titles):
        return False
    if not has_any(title, prefs.include_titles or DEFAULT_TITLES, hyphen_joins=True):
        return False
    return location_ok(job.location, prefs)


async def get_for(s: AsyncSession, user_id: UUID) -> Preferences | None:
    user = await s.get(User, user_id)
    return Preferences.model_validate(user.preferences or {}) if user else None


async def save_for(s: AsyncSession, user_id: UUID, prefs: Preferences) -> Preferences | None:
    user = await s.get(User, user_id)
    if user is None:
        return None
    user.preferences = prefs.model_dump()
    await s.commit()
    from app.services.matching_services import match_all   # local import: matching imports this module
    await match_all(s, user_id=user_id)                     # new filters show up now, not at the next cron run
    return prefs
