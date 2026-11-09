import io
from uuid import UUID

from docx import Document
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Resume

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = (".pdf", ".docx", ".txt")


class TooLarge(Exception):
    pass


class UnsupportedType(Exception):
    pass


def sniff(data: bytes) -> str:
    """Decide the file type from its first bytes, not its name."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    if b"\x00" in data:
        raise UnsupportedType                      # binary pretending to be text
    return "txt"


def extract_text(data: bytes) -> str:
    kind = sniff(data)
    if kind == "pdf":
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    if kind == "docx":
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="ignore")


async def create(s: AsyncSession, user_id: UUID, filename: str, data: bytes) -> Resume:
    if not filename.lower().endswith(ALLOWED):
        raise UnsupportedType
    if len(data) > MAX_BYTES:
        raise TooLarge
    text = extract_text(data).replace("\x00", "")  # belt and braces: Postgres rejects NUL in text
    # one resume per user: replace, don't pile up. ON DELETE CASCADE drops its old match scores.
    await s.execute(delete(Resume).where(Resume.user_id == user_id))
    resume = Resume(user_id=user_id, filename=filename, raw_text=text)
    s.add(resume)
    await s.commit()
    return resume


async def list_for(s: AsyncSession, user_id: UUID) -> list[Resume]:
    return list((await s.execute(select(Resume).where(Resume.user_id == user_id))).scalars().all())


async def upload(s: AsyncSession, user_id: UUID, filename: str, data: bytes) -> Resume:
    """Save (replacing any previous resume), tag, and match this user now instead of at the next cron run."""
    from app.services.matching_services import match_all, tag_resumes
    resume = await create(s, user_id, filename, data)
    await tag_resumes(s)
    await match_all(s, user_id=user_id)
    return resume
