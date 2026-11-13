"""Walk a big query a slice at a time so memory stays flat no matter how many rows match."""

from collections.abc import AsyncIterator

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

BATCH = 200


async def batches(s: AsyncSession, stmt: Select, key, size: int | None = None) -> AsyncIterator[list]:
    """Yield rows a batch at a time in `key` order (keyset pagination: no OFFSET, each page is an index seek).

    The caller commits each batch before asking for the next. Committed rows are only weakly held by the
    session, so finished batches are freed: a run over 100k rows holds about one batch, and a crash keeps
    everything committed so far."""
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
