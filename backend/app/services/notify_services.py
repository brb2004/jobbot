import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_core import get_settings
from app.db.models_db import User

log = logging.getLogger(__name__)


async def confirmed_count(s: AsyncSession) -> int:
    return await s.scalar(select(func.count()).select_from(User).where(User.email_verified_at.is_not(None)))


async def notify(message: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
    url = get_settings().NOTIFY_URL
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5, transport=transport) as client:
            await client.post(url, content=message.encode(), headers={"Title": "SkillFit", "Tags": "tada"})
    except httpx.HTTPError:
        log.warning("notification failed")
