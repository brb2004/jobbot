from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config_core import get_settings

engine = create_async_engine(get_settings().DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

def get_sessionmaker():
    """For work that runs after the response (background tasks): the request's session is closed by then."""
    return SessionLocal


async def get_session():
    async with SessionLocal() as s:
        yield s