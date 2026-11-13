import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://jobbot:jobbot123@localhost:55432/jobbot_test"
)
if not os.environ["DATABASE_URL"].rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("Refusing to run tests: DATABASE_URL is not a *_test database")

from contextlib import asynccontextmanager
from datetime import UTC
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps_api, limits_api
from app.core.db_core import engine, get_session, get_sessionmaker
from app.core.security_core import create_access_token
from app.db.models_db import Base
from app.main import app


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

        @asynccontextmanager
        async def same_session():
            yield s

        app.dependency_overrides[get_sessionmaker] = lambda: same_session
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
    from datetime import datetime

    from app.db.models_db import User

    user = User(
        id=uuid4(),
        email=f"{uuid4().hex[:12]}@fixture.test",
        hashed_password="x",
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limits_api.reset_all()
    yield


@pytest.fixture(autouse=True)
def _no_real_email():

    async def drop(msg):
        pass

    app.dependency_overrides[deps_api.get_mailer] = lambda: drop
    yield
    app.dependency_overrides.pop(deps_api.get_mailer, None)


@pytest.fixture(autouse=True)
def _fresh_job_index():
    from app.services import job_index_services

    job_index_services._cached = None
    yield
    job_index_services._cached = None


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    from app.ingest import crawl_ingest

    monkeypatch.setattr(crawl_ingest, "BACKOFF", 0)


def user_row(**kw):
    from datetime import datetime

    from app.db.models_db import User

    return User(
        **{
            "id": uuid4(),
            "email": f"{uuid4().hex[:12]}@fixture.test",
            "hashed_password": "x",
            "email_verified_at": datetime.now(UTC),
            **kw,
        }
    )


async def signup(client, email: str, password: str = "correct-horse-battery") -> str:
    r = await client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 202, r.text
    r = await client.post("/auth/login?token=1", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
