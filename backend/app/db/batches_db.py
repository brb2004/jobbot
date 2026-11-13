from collections.abc import AsyncIterator

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

BATCH = 200


async def batches(s: AsyncSession, stmt: Select, key, size: int | None = None) -> AsyncIterator[list]:
    last = None
    while True:
        page = stmt.order_by(key).limit(size or BATCH)
        if last is not None:
            page = page.where(key > last)
        rows = (await s.scalars(page)).all()
        if not rows:
            return
        last = getattr(rows[-1], key.key)
        yield rows
