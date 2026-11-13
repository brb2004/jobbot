import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security_core import (
    hash_password,
    make_reset_token,
    reset_token_user,
    reset_token_valid,
    verify_password,
    verify_token_valid,
)
from app.db.models_db import Resume, User

# Checked against when the email doesn't exist, so both failures take the same time.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


class EmailTaken(Exception):
    pass


async def register(s: AsyncSession, email: str, password: str) -> User:
    hashed = await asyncio.to_thread(
        hash_password, password
    )  # bcrypt is ~175 ms of CPU: keep it off the event loop
    user = User(email=email.lower(), hashed_password=hashed)
    s.add(user)
    try:
        await s.commit()
    except IntegrityError:
        await s.rollback()
        raise EmailTaken from None
    return user


async def authenticate(s: AsyncSession, email: str, password: str) -> User | None:
    user = (await s.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    if user is None or len(password.encode()) > 72:  # >72 bytes can't match (and would make bcrypt raise)
        await asyncio.to_thread(verify_password, "x", _DUMMY_HASH)  # burn the same time as a real check
        return None
    ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
    return user if ok else None


async def by_email(s: AsyncSession, email: str) -> User | None:
    return (await s.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()


async def get(s: AsyncSession, user_id: UUID) -> User | None:
    return await s.get(User, user_id)


async def delete_account(s: AsyncSession, user_id: UUID) -> None:
    """User + resume; match scores go with the resume (ON DELETE CASCADE). Their tokens die with the row."""
    await s.execute(delete(Resume).where(Resume.user_id == user_id))
    await s.execute(delete(User).where(User.id == user_id))
    await s.commit()


async def reset_link_token(s: AsyncSession, email: str) -> tuple[User, str] | None:
    user = (await s.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
    return None if user is None else (user, make_reset_token(str(user.id), user.hashed_password))


async def reset_password(s: AsyncSession, token: str, new_password: str) -> bool:
    claimed = reset_token_user(token)
    try:
        user_id = UUID(claimed) if claimed else None
    except ValueError:
        user_id = None
    user = await s.get(User, user_id) if user_id else None
    if user is None or not reset_token_valid(token, user.hashed_password):
        return False
    user.hashed_password = await asyncio.to_thread(hash_password, new_password)
    user.tokens_valid_after = datetime.now(UTC)  # sign out every existing session
    await s.commit()
    return True


async def _claimed_user(s: AsyncSession, token: str) -> User | None:
    claimed = reset_token_user(token)  # resets and confirmations share the token shape
    try:
        return await s.get(User, UUID(claimed)) if claimed else None
    except ValueError:
        return None


async def confirm_email(s: AsyncSession, token: str) -> tuple[User, bool] | None:
    """(user, True) on the click that confirms, (user, False) on later clicks, None if the link is bad."""
    user = await _claimed_user(s, token)
    if user is None or not verify_token_valid(token, user.email):
        return None
    if user.email_verified_at is not None:  # clicking the link twice is fine
        return user, False
    user.email_verified_at = datetime.now(UTC)
    await s.commit()
    return user, True
