"""Dev tool. No args: coverage report.  With a board: save its first missed posting as a fixture + show headings."""
import asyncio
import re
import sys
from pathlib import Path
from collections import Counter

from sqlalchemy import select

from app.core.db_core import SessionLocal, engine
from app.db.models_db import Job
from app.ingest.sections_ingest import requirement_bullets


async def main(board: str | None) -> None:
    async with SessionLocal() as s:
        stmt = select(Job.board, Job.content_html).where(Job.content_html.is_not(None))
        if board:
            stmt = stmt.where(Job.board == board)
        rows = (await s.execute(stmt)).all()
    await engine.dispose()

    misses = [(b, h) for b, h in rows if not requirement_bullets(h)]
    if not board:
        total = len(rows)
        print(f"found bullets in {total - len(misses)}/{total} jobs ({100 * (total - len(misses)) / total:.0f}%)")
        print("boards with the most misses:", Counter(b for b, _ in misses).most_common(8))
        return

    if not misses:
        print(f"{board}: no misses")
        return
    path, n = f"tests/fixtures/{board}.html", 2
    while Path(path).exists():                      # never overwrite a fixture that guards an earlier fix
        path, n = f"tests/fixtures/{board}_{n}.html", n + 1
    open(path, "w").write(misses[0][1])
    print(f"{board}: {len(misses)}/{len(rows)} missed; saved one to {path}\n")
    for tag in re.findall(r"<(?:h[1-6]|strong|b)>[^<]{3,60}", misses[0][1])[:25]:
        print(tag)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
