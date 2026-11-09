import asyncio
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security_core import hash_password, verify_password
from app.db.models_db import Resume, User

# Checked against when the email doesn't exist, so both failures take the same time.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


class EmailTaken(Exception):
    pass


async def register(s: AsyncSession, email: str, password: str) -> User:
    hashed = await asyncio.to_thread(hash_password, password)   # bcrypt is ~175 ms of CPU: keep it off the event loop
    user = User(email=email.lower(), hashed_password=hashed)
    s.add(user)
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise EmailTaken
    return user


async def authenticate(s: AsyncSession, email: str, password: str) -> User | None:
    user = (await s.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    if user is None or len(password.encode()) > 72:   # >72 bytes can't match (and would make bcrypt raise)
        await asyncio.to_thread(verify_password, "x", _DUMMY_HASH)   # burn the same time as a real check
        return None
    ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
    return user if ok else None


async def get(s: AsyncSession, user_id: UUID) -> User | None:
    return await s.get(User, user_id)


async def delete_account(s: AsyncSession, user_id: UUID) -> None:
    """User + resume; match scores go with the resume (ON DELETE CASCADE). Their tokens die with the row."""
    await s.execute(delete(Resume).where(Resume.user_id == user_id))
    await s.execute(delete(User).where(User.id == user_id))
    await s.commit()
