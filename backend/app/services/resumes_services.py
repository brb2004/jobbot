import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Resume, User

# parsing lives in documents_services (child process, time and page limits); re-exported for callers
from app.services.documents_services import (
    TooLarge,
    Unreadable,
    UnsupportedType,
    extract_text_safely,
)
from app.services.experience_services import years_from_resume
from app.services.matching_services import rematch_user
from app.services.preferences_services import Preferences, ResumePrefs, for_resume
from app.services.skills_services import default_tagger
from app.services.tagging_services import tag_resumes

MAX_BYTES = 2 * 1024 * 1024
ALLOWED = (".pdf", ".docx", ".txt")


def safe_filename(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "", base).strip(" .")
    stem, dot, ext = base.rpartition(".")
    if dot and len(base) > 100:
        base = stem[: 100 - len(ext) - 1] + "." + ext
    return base[:100] or "resume"


MAX_RESUMES = 2


class TooMany(Exception):
    pass


class NotFound(Exception):
    pass


def default_name(filename: str) -> str:
    stem = filename.rpartition(".")[0] or filename
    return re.sub(r"[_\-]+", " ", stem).strip()[:40] or "Resume"


async def _mine(s: AsyncSession, user_id: UUID, resume_id: UUID) -> Resume:
    resume = await s.get(Resume, resume_id)
    if resume is None or resume.user_id != user_id:
        raise NotFound  # someone else's id looks the same as a missing one
    return resume


async def create(
    s: AsyncSession,
    user_id: UUID,
    filename: str,
    data: bytes,
    require_skills: bool = False,
    replace: UUID | None = None,
    name: str | None = None,
) -> Resume:
    filename = safe_filename(filename)
    if not filename.lower().endswith(ALLOWED):
        raise UnsupportedType
    if len(data) > MAX_BYTES:
        raise TooLarge
    text = (await extract_text_safely(data)).replace("\x00", "")  # child process, time-limited
    # validate BEFORE deleting anything: a bad upload must never wipe the current resume
    if not text.strip():
        raise Unreadable(
            "Couldn't read any text from this file. If it's a scanned image, upload a text-based PDF or .docx."
        )
    tagger = default_tagger()
    if require_skills and not tagger.tag(text):
        raise Unreadable(
            "Couldn't find any skills in this file. Check it's your resume, "
            "or add skills on the Preferences page."
        )
    # Lock the user row: two uploads at once take turns, so the count check below can't be raced past.
    await s.execute(select(User.id).where(User.id == user_id).with_for_update())
    keep: dict = {}
    if replace is not None:
        old = await _mine(s, user_id, replace)
        keep = {"name": old.name, "title_prefs": old.title_prefs, "created_at": old.created_at}
        await s.delete(old)  # ON DELETE CASCADE drops its old match scores
        await s.flush()
    elif (
        await s.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))
        >= MAX_RESUMES
    ):
        raise TooMany
    resume = Resume(
        user_id=user_id,
        filename=filename,
        raw_text=text,
        years_detected=years_from_resume(text, has_skills=lambda t: bool(tagger.pattern.search(t))),
        **{**keep, "name": (name or "").strip()[:40] or keep.get("name") or default_name(filename)},
    )
    s.add(resume)
    await s.commit()
    return resume


async def list_for(s: AsyncSession, user_id: UUID) -> list[Resume]:
    stmt = select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at, Resume.id)
    return list((await s.execute(stmt)).scalars().all())


async def upload(
    s: AsyncSession,
    user_id: UUID,
    filename: str,
    data: bytes,
    replace: UUID | None = None,
    name: str | None = None,
) -> Resume:
    resume = await create(s, user_id, filename, data, require_skills=True, replace=replace, name=name)
    await tag_resumes(s)
    await rematch_user(s, user_id)
    return resume


async def update(
    s: AsyncSession, user_id: UUID, resume_id: UUID, name: str | None, own: ResumePrefs | None
) -> Resume:
    resume = await _mine(s, user_id, resume_id)
    if name is not None:
        resume.name = name.strip()[:40] or resume.name
    if own is not None:
        user = await s.get(User, user_id)
        for_resume(
            Preferences.model_validate(user.preferences or {}), own.model_dump()
        )  # raises on a conflict
        resume.title_prefs = (
            own.model_dump() if any(v is not None for v in own.model_dump().values()) else None
        )
    await s.commit()
    if own is not None:
        await rematch_user(s, user_id)
    return resume


async def remove(s: AsyncSession, user_id: UUID, resume_id: UUID) -> None:
    await s.delete(await _mine(s, user_id, resume_id))  # its match scores go with it
    await s.commit()
