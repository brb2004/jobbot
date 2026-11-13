from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, User
from app.services.locations_services import location_blocked, location_ok
from app.services.title_rules_services import title_ok

Word = Annotated[str, Field(min_length=1, max_length=50)]


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_titles: list[Word] = Field(default=[], max_length=50)
    exclude_titles: list[Word] = Field(default=[], max_length=50)
    locations: list[Word] = Field(default=[], max_length=50)
    remote: bool = True
    onsite: bool = True
    years_experience: int | None = Field(default=None, ge=0, le=60)
    extra_skills: list[Word] = Field(default=[], max_length=50)
    include_presales: bool = False

    @field_validator("include_titles", "exclude_titles", "locations", "extra_skills")
    @classmethod
    def _clean(cls, words: list[str], info) -> list[str]:
        keep_case = info.field_name == "extra_skills"
        out, seen = [], set()
        for w in words:
            w = w.strip()
            if not w:
                raise ValueError("entries can't be blank")
            w = w if keep_case else w.lower()
            if w.lower() not in seen:
                seen.add(w.lower())
                out.append(w)
        return out

    @model_validator(mode="before")
    @classmethod
    def _legacy_locations(cls, data):
        if not isinstance(data, dict):
            return data
        old = list(data.get("locations") or [])
        if "remote_regions" not in data and not any(str(loc).strip().lower() == "remote" for loc in old):
            return data
        data = dict(data)
        regions = data.pop("remote_regions", None) or []
        places = [loc for loc in old if str(loc).strip().lower() != "remote"]
        wants_remote = len(places) != len(old)
        if wants_remote and not places:
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


class ResumePrefs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_titles: list[Word] | None = Field(default=None, max_length=50)
    exclude_titles: list[Word] | None = Field(default=None, max_length=50)
    years_experience: int | None = Field(default=None, ge=0, le=60)

    @field_validator("include_titles", "exclude_titles")
    @classmethod
    def _clean(cls, words, info):
        return None if words is None else Preferences._clean(words, info)


def for_resume(account: Preferences, own: dict | None) -> Preferences:
    over = {k: v for k, v in (own or {}).items() if v is not None}
    if not over:
        return account
    merged = {**account.model_dump(), **over}
    if "include_titles" in over and "exclude_titles" not in over:
        merged["exclude_titles"] = [w for w in merged["exclude_titles"] if w not in over["include_titles"]]
    if "exclude_titles" in over and "include_titles" not in over:
        merged["include_titles"] = [w for w in merged["include_titles"] if w not in over["exclude_titles"]]
    return Preferences.model_validate(merged)


def allowed(job: Job, prefs: Preferences) -> bool:
    if location_blocked(job.location):
        return False
    title_fits = title_ok(job.title or "", prefs.include_titles, prefs.exclude_titles, prefs.include_presales)
    return title_fits and location_ok(job.location, prefs)


async def get_for(s: AsyncSession, user_id: UUID) -> Preferences | None:
    user = await s.get(User, user_id)
    return Preferences.model_validate(user.preferences or {}) if user else None


async def save_for(s: AsyncSession, user_id: UUID, prefs: Preferences) -> Preferences | None:
    user = await s.get(User, user_id)
    if user is None:
        return None
    user.preferences = prefs.model_dump()
    await s.commit()
    return prefs
