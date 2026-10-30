from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security_core import hash_password
from app.db.models_db import User


async def register(s: AsyncSession, email: str, password: str) -> User:
    user = User(email=email.lower(), hashed_password=hash_password(password))
    s.add(user)
    await s.commit()
    return user


async def get(s: AsyncSession, user_id: UUID) -> User | None:
    return await s.get(User, user_id)