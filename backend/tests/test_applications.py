from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.security_core import create_access_token
from app.db.models_db import Job, Resume, User
from app.services.matching_services import match_all

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _show_two(monkeypatch):
    """Show 2 matches so a third stored one is the reserve that moves up."""
    import app.services.matches_services as matches

    monkeypatch.setattr(matches, "SHOW", 2)


async def setup(session, n=3):
    user = User(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@apply.test",
        hashed_password="x",
        email_verified_at=datetime.now(UTC),
    )
    jobs = [
        Job(
            title=f"Backend Engineer {i}",
            board=f"acme{i}",
            skills=["Python"],
            requirements=["Python"],
            url=f"https://x/{i}",
        )
        for i in range(n)
    ]
    session.add_all([user, *jobs, Resume(user_id=user.id, skills=["Python"])])
    await session.flush()
    await match_all(session, k=2)  # 2 shown, the rest stored as reserve
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}, jobs


async def shown(client, h):
    return {m["job_id"] for m in (await client.get("/dashboard", headers=h)).json()}


async def test_applying_moves_the_job_to_applied_and_the_next_match_up(client, session):
    h, jobs = await setup(session)
    before = await shown(client, h)
    assert len(before) == 2
    picked = next(iter(before))
    assert (await client.put(f"/applications/{picked}", headers=h)).status_code == 204
    after = await shown(client, h)
    assert picked not in after and len(after) == 2  # the reserve job moved up
    applied = (await client.get("/applications", headers=h)).json()
    assert [a["job_id"] for a in applied] == [picked] and applied[0]["closed"] is False


async def test_undo_puts_it_back(client, session):
    h, jobs = await setup(session, n=2)
    job = str(jobs[0].id)
    await client.put(f"/applications/{job}", headers=h)
    assert job not in await shown(client, h)
    assert (await client.delete(f"/applications/{job}", headers=h)).status_code == 204
    assert job in await shown(client, h)
    assert (await client.get("/applications", headers=h)).json() == []


async def test_marking_twice_is_harmless_and_unknown_jobs_404(client, session):
    h, jobs = await setup(session, n=1)
    for _ in range(2):
        assert (await client.put(f"/applications/{jobs[0].id}", headers=h)).status_code == 204
    assert len((await client.get("/applications", headers=h)).json()) == 1
    assert (await client.put(f"/applications/{uuid4()}", headers=h)).status_code == 404


async def test_not_interested_hides_it_without_listing_it_as_applied(client, session):
    h, jobs = await setup(session)
    picked = next(iter(await shown(client, h)))
    assert (await client.put(f"/applications/{picked}?status=dismissed", headers=h)).status_code == 204
    after = await shown(client, h)
    assert picked not in after and len(after) == 2  # next match moved up
    assert (await client.get("/applications", headers=h)).json() == []
    assert (
        await client.put(f"/applications/{picked}", headers=h)
    ).status_code == 204  # changed mind: applied
    assert [a["job_id"] for a in (await client.get("/applications", headers=h)).json()] == [picked]
    assert (await client.put(f"/applications/{picked}?status=bogus", headers=h)).status_code == 422


async def test_marking_and_undo_never_rerun_matching(client, session, monkeypatch):
    """The whole point of the reserve: a click is a cheap insert, not a full rematch over every job."""
    h, jobs = await setup(session)
    import app.services.matching_services as matching

    calls = []

    async def spy(*a, **k):
        calls.append(1)

    monkeypatch.setattr(matching, "match_all", spy)
    picked = next(iter(await shown(client, h)))
    await client.put(f"/applications/{picked}", headers=h)
    await client.put(f"/applications/{picked}?status=dismissed", headers=h)
    await client.delete(f"/applications/{picked}", headers=h)
    assert calls == []


async def test_closed_jobs_leave_the_dashboard_right_away(client, session):
    from datetime import datetime

    h, jobs = await setup(session)
    before = await shown(client, h)
    gone = next(j for j in jobs if str(j.id) in before)
    gone.closed_at = datetime.now(UTC)
    await session.flush()
    after = await shown(client, h)
    assert str(gone.id) not in after and len(after) == 2  # reserve fills the slot
