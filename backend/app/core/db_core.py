from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config_core import get_settings

engine = create_async_engine(get_settings().DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def get_sessionmaker():
    return SessionLocal


async def get_session():
    async with SessionLocal() as s:
        yield s
