import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://jobbot:jobbot123@localhost:55432/jobbot_test")
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.db import engine
from app.db.models import Base

@pytest.fixture(scope="session", autouse=True)
async def tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c