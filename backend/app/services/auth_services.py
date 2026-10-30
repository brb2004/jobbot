from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security_core import hash_password, verify_password
from app.db.models_db import User

# Checked against when the email doesn't exist, so both failures take the same time.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


class EmailTaken(Exception):
    pass


async def register(s: AsyncSession, email: str, password: str) -> User:
    user = User(email=email.lower(), hashed_password=hash_password(password))
    s.add(user)
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise EmailTaken
    return user


async def authenticate(s: AsyncSession, email: str, password: str) -> User | None:
    user = (await s.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    if user is None:
        verify_password(password, _DUMMY_HASH)     # burn the same time as a real check
        return None
    return user if verify_password(password, user.hashed_password) else None


async def get(s: AsyncSession, user_id: UUID) -> User | None:
    return await s.get(User, user_id)