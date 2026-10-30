import io
from uuid import UUID

from docx import Document
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Resume

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = (".pdf", ".docx", ".txt")


class TooLarge(Exception):
    pass


class UnsupportedType(Exception):
    pass


def extract_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="ignore")


async def create(s: AsyncSession, user_id: UUID, filename: str, data: bytes) -> Resume:
    if not filename.lower().endswith(ALLOWED):
        raise UnsupportedType
    if len(data) > MAX_BYTES:
        raise TooLarge
    resume = Resume(user_id=user_id, filename=filename, raw_text=extract_text(data, filename))
    s.add(resume)
    await s.commit()
    return resume


async def list_for(s: AsyncSession, user_id: UUID) -> list[Resume]:
    return list((await s.execute(select(Resume).where(Resume.user_id == user_id))).scalars().all())