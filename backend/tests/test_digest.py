import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db.models_db import Job, MatchScore, Resume
from app.schemas.matches_schemas import MatchOut
from app.services import digest_services as digest
from app.services.digest_render_services import render
from app.services.scoring_services import tier
from app.services.seen_services import mark_seen
from tests.conftest import user_row


def m(title, score):
    return MatchOut(job_id=uuid4(), title=title, score=score)


def test_digest_lists_top_matches_best_first():
    matches = [m("Data", 0.6), m("Backend", 0.9), m("Platform", 0.8)]

    body = digest.render(matches, top_n=2)

    assert body.index("Backend") < body.index("Platform")
    assert "Data" not in body


def test_digest_with_no_matches_says_so():
    assert "no new matches" in digest.render([], top_n=5).lower()


async def test_jobs_already_seen_are_still_open_not_new(session):
    owner = user_row()
    seen_job, fresh_job = Job(title="Seen", url="https://x/s"), Job(title="Fresh", url="https://x/f")
    resume = Resume(user=owner)
    session.add_all([seen_job, fresh_job, resume])
    await session.flush()
    session.add_all([MatchScore(resume_id=resume.id, job_id=j.id, score=0.8) for j in (seen_job, fresh_job)])
    await mark_seen(session, owner.id, [seen_job.id])
    await session.commit()
    sender = FakeSender()

    assert await digest.send_weekly(session, sender, now=datetime(2026, 11, 2, tzinfo=UTC)) == 1

    [(_, body)] = sender.sent
    new, still = body.split("Still open from earlier:")
    assert "Fresh" in new and "Seen" not in new and "Seen — https://x/s" in still


class FakeSender:
    def __init__(self):
        self.sent = []

    async def send(self, user_id, body):
        self.sent.append((user_id, body))


async def test_sends_one_email_per_user_with_new_matches(session):
    alice, bob, carol = user_row(), user_row(), user_row()
    job = Job(title="Backend")
    r_alice, r_bob, r_carol = Resume(user=alice), Resume(user=bob), Resume(user=carol)
    session.add_all([job, r_alice, r_bob, r_carol])
    await session.flush()
    session.add_all([MatchScore(resume_id=r.id, job_id=job.id, score=0.9) for r in (r_alice, r_bob, r_carol)])
    await mark_seen(session, carol.id, [job.id])
    await session.commit()
    sender = FakeSender()

    sent = await digest.send_weekly(session, sender, now=datetime(2026, 11, 2, tzinfo=UTC))

    assert sent == 2
    assert {user_id for user_id, _ in sender.sent} == {alice.id, bob.id}


def test_each_match_shows_its_link_and_what_you_have_and_lack():
    match = MatchOut(
        job_id=uuid4(),
        title="Backend",
        score=0.5,
        url="https://x/1",
        detail={"met": ["Python"], "partial": ["Docker and K8s"], "missing": ["Go"], "soft": []},
    )

    body = digest.render([match], top_n=5)

    assert "https://x/1" in body
    assert "Python" in body and "Docker and K8s" in body and "Go" in body


def test_tier_labels():
    assert tier(0.51) == "Strong match"
    assert tier(0.30) == "Worth applying"
    assert tier(0.12) == "Stretch"


def test_render_says_how_many_of_the_skills_you_have():
    m = MatchOut(
        job_id=uuid.uuid4(),
        title="Backend",
        score=0.5,
        url="https://x/1",
        detail={"met": ["Python", "Go"], "partial": [], "missing": ["Kafka"]},
    )
    assert "Backend — " in render([m], 20) and "· 2 of 3 skills" in render([m], 20)


def test_render_shows_tier_and_years_flag_instead_of_percent():
    m = MatchOut(
        job_id=uuid.uuid4(),
        title="Backend",
        score=0.25,
        url="https://x/1",
        detail={"met": ["Python"], "missing": [], "years_asked": 3, "over_years": True},
    )
    text = render([m], 20)
    assert "Backend — Stretch · asks for 3+ years" in text
    assert "%" not in text


class FlakySender(FakeSender):
    def __init__(self, broken):
        super().__init__()
        self.broken = broken

    async def send(self, user_id, body):
        if user_id in self.broken:
            raise OSError("SMTP said no")
        await super().send(user_id, body)


async def _three_users_with_matches(session, now):
    users = [user_row() for _ in range(3)]
    job = Job(title="Backend")
    resumes = [Resume(user=u) for u in users]
    session.add_all([job, *resumes])
    await session.flush()
    session.add_all([MatchScore(resume_id=r.id, job_id=job.id, score=0.9, scored_at=now) for r in resumes])
    await session.commit()
    return [u.id for u in users]


async def test_one_failed_email_doesnt_stop_the_others(session):
    now = datetime(2026, 11, 2, tzinfo=UTC)
    a, b, c = await _three_users_with_matches(session, now)
    sender = FlakySender(broken={b})
    assert await digest.send_weekly(session, sender, now=now) == 2
    assert {u for u, _ in sender.sent} == {a, c}


async def test_rerunning_the_same_week_sends_nothing_twice_but_retries_failures(session):
    now = datetime(2026, 11, 2, tzinfo=UTC)
    a, b, c = await _three_users_with_matches(session, now)
    await digest.send_weekly(session, FlakySender(broken={b}), now=now)
    second = FakeSender()
    assert await digest.send_weekly(session, second, now=now) == 1
    assert [u for u, _ in second.sent] == [b]
    assert await digest.send_weekly(session, FakeSender(), now=now + timedelta(days=7)) == 0
    fresh = Job(title="Platform")
    session.add(fresh)
    await session.flush()
    resumes = (await session.scalars(select(Resume).where(Resume.user_id.in_([a, b, c])))).all()
    session.add_all([MatchScore(resume_id=r.id, job_id=fresh.id, score=0.8) for r in resumes])
    await session.commit()
    assert await digest.send_weekly(session, FakeSender(), now=now + timedelta(days=7)) == 3
