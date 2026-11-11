import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Resume, User
# parsing lives in documents_services (child process, time and page limits); re-exported for callers
from app.services.documents_services import (TooLarge, Unreadable, UnsupportedType,  # noqa: F401
                                             extract_text, extract_text_safely, sniff)

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = (".pdf", ".docx", ".txt")


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
    text = (await extract_text_safely(data)).replace("\x00", "")  # child process, time-limited
    # validate BEFORE deleting anything: a bad upload must never wipe the current resume
    if not text.strip():
        raise Unreadable("Couldn't read any text from this file. If it's a scanned image, upload a text-based PDF or .docx.")
    if require_skills:
        from app.services.skills_services import default_tagger
        if not default_tagger().tag(text):
            raise Unreadable("Couldn't find any skills in this file. Check it's your resume, "
                             "or add skills on the Preferences page.")
    # one resume per user (UNIQUE): replace, don't pile up. ON DELETE CASCADE drops its old match scores.
    # Lock the user row first so two uploads at once take turns instead of one hitting the constraint.
    await s.execute(select(User.id).where(User.id == user_id).with_for_update())
    await s.execute(delete(Resume).where(Resume.user_id == user_id))
    from app.services.experience_services import years_from_resume; from app.services.skills_services import default_tagger
    resume = Resume(user_id=user_id, filename=filename, raw_text=text, years_detected=years_from_resume(text, has_skills=lambda t: bool(default_tagger().pattern.search(t))))
    s.add(resume)
    await s.commit()
    return resume


async def list_for(s: AsyncSession, user_id: UUID) -> list[Resume]:
    return list((await s.execute(select(Resume).where(Resume.user_id == user_id))).scalars().all())


async def upload(s: AsyncSession, user_id: UUID, filename: str, data: bytes) -> Resume:
    """Save (replacing any previous resume), tag, and match this user now instead of at the next cron run."""
    from app.services.matching_services import rematch_user, tag_resumes
    resume = await create(s, user_id, filename, data, require_skills=True)
    await tag_resumes(s)
    await rematch_user(s, user_id)
    return resume
