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


@pytest_asyncio.fixture
async def auth_headers(session):
    """A real user row (tokens for users that don't exist are rejected), rolled back with the test."""
    from datetime import datetime, timezone
    from app.db.models_db import User
    user = User(id=uuid4(), email=f"{uuid4().hex[:12]}@fixture.test", hashed_password="x",
                email_verified_at=datetime.now(timezone.utc))
    session.add(user)
    await session.flush()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}



import pytest as _pytest


@_pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate limiters are process-wide; give every test a clean slate."""
    from app.api.routes import auth_routes
    for limiter in (auth_routes.LOGIN_FAILS, auth_routes.LOGIN_IP, auth_routes.REGISTER_IP,
                    auth_routes.FORGOT_IP, auth_routes.FORGOT_EMAIL,
                    auth_routes.VERIFY_RESEND):
        limiter.reset()
    yield


@_pytest.fixture(autouse=True)
def _no_real_email():
    """.envrc holds real SMTP credentials: tests must never send mail. Tests that check mail swap in an outbox."""
    from app.api.routes import auth_routes

    async def drop(msg):
        pass

    app.dependency_overrides[auth_routes.get_mailer] = lambda: drop
    yield
    app.dependency_overrides.pop(auth_routes.get_mailer, None)


@_pytest.fixture(autouse=True)
def _fresh_job_index():
    """The cached job index is process-wide; each test starts without one."""
    from app.services import matching_services
    matching_services._cached = None
    yield
    matching_services._cached = None
