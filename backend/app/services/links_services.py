from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import User

MAX_URL = 200


class Links(BaseModel):
    model_config = ConfigDict(extra="forbid")
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None

    @field_validator("linkedin", "github", "website", mode="before")
    @classmethod
    def _url(cls, value):
        return web_address(value)


def web_address(value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > MAX_URL or any(c.isspace() or c in "<>\"'" for c in text):
        raise ValueError("enter a web address like https://github.com/you")
    if "://" not in text:
        text = "https://" + text
    host = urlsplit(text).hostname or ""
    if urlsplit(text).scheme not in ("http", "https") or "." not in host:
        raise ValueError("enter a web address like https://github.com/you")
    return text


async def get_for(s: AsyncSession, user_id: UUID) -> Links | None:
    user = await s.get(User, user_id)
    return Links.model_validate(user.links or {}) if user else None


async def save_for(s: AsyncSession, user_id: UUID, links: Links) -> Links | None:
    user = await s.get(User, user_id)
    if user is None:
        return None
    user.links = links.model_dump()
    await s.commit()
    return links
