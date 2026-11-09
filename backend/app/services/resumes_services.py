import io
import re
import zipfile
from uuid import UUID

from docx import Document
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Resume

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = (".pdf", ".docx", ".txt")
MAX_UNZIPPED = 10 * 1024 * 1024     # a .docx is a zip: cap what it expands to (zip bombs)
MAX_ZIP_ENTRIES = 1000


class TooLarge(Exception):
    pass


class UnsupportedType(Exception):
    pass


class Unreadable(Exception):
    """The file parsed but is unusable as a resume. str(exc) is the user-facing reason."""


def sniff(data: bytes) -> str:
    """Decide the file type from its first bytes, not its name."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    if b"\x00" in data:
        raise UnsupportedType                      # binary pretending to be text
    return "txt"


def _check_zip(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries = z.infolist()
    except zipfile.BadZipFile:
        raise Unreadable("Couldn't read this .docx. Try saving it again, or upload a PDF.") from None
    if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > MAX_UNZIPPED:
        raise Unreadable("This .docx is too large once unpacked.")


def extract_text(data: bytes) -> str:
    kind = sniff(data)
    try:
        if kind == "pdf":
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        if kind == "docx":
            _check_zip(data)
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except Unreadable:
        raise
    except Exception:
        # never a 500, and never echo parser internals (which can contain resume text)
        raise Unreadable("Couldn't read this file. Try saving it again as a PDF or .docx.") from None
    return data.decode("utf-8", errors="ignore")


def safe_filename(name: str) -> str:
    """Basename only; no path, markup or control characters; capped length. Display-only, never a disk path."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "", base).strip(" .")
    stem, dot, ext = base.rpartition(".")
    if dot and len(base) > 100:
        base = stem[: 100 - len(ext) - 1] + "." + ext
    return base[:100] or "resume"


async def create(s: AsyncSession, user_id: UUID, filename: str, data: bytes,
                 require_skills: bool = False) -> Resume:
    filename = safe_filename(filename)
    if not filename.lower().endswith(ALLOWED):
        raise UnsupportedType
    if len(data) > MAX_BYTES:
        raise TooLarge
    text = extract_text(data).replace("\x00", "")  # belt and braces: Postgres rejects NUL in text
    # validate BEFORE deleting anything: a bad upload must never wipe the current resume
    if not text.strip():
        raise Unreadable("Couldn't read any text from this file. If it's a scanned image, upload a text-based PDF or .docx.")
    if require_skills:
        from app.services.skills_services import default_tagger
        if not default_tagger().tag(text):
            raise Unreadable("Couldn't find any skills in this file. Check it's your resume, "
                             "or add skills on the Preferences page.")
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
    resume = await create(s, user_id, filename, data, require_skills=True)
    await tag_resumes(s)
    await match_all(s, user_id=user_id)
    return resume
