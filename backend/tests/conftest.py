# 1. env vars FIRST, before anything from app/ is imported
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://jobbot:jobbot123@localhost:55432/jobbot_test")
if not os.environ["DATABASE_URL"].rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("Refusing to run tests: DATABASE_URL is not a *_test database")

# 2. then imports
from uuid import uuid4
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.db_core import engine, get_session
from app.core.security_core import create_access_token
from app.db.models_db import Base


# 3. fixtures
@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def session():
    async with engine.connect() as conn:
        trans = await conn.begin()
        s = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        app.dependency_overrides[get_session] = lambda: s
        yield s
        app.dependency_overrides.clear()
        await s.close()
        await trans.rollback()


@pytest_asyncio.fixture
async def client(session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {create_access_token(str(uuid4()))}"}


def test_include_titles_require_one_of_the_words():
    prefs = Preferences(include_titles=["engineer", "developer"])
    assert allowed(Job(title="IT Systems Engineer"), prefs)
    assert not allowed(Job(title="Account Executive, Platforms"), prefs)
    assert allowed(Job(title="Anything"), Preferences())        # no include list = everything allowed