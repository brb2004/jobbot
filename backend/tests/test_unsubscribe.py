"""Weekly email unsubscribe: footer link + RFC 8058 one-click header; signed token, POST only."""
from datetime import datetime, timezone

from app.core.security_core import make_reset_token, make_unsubscribe_token
from app.db.models_db import Job, MatchScore, Resume, User
from app.services.digest_services import send_weekly
from app.services.email_services import EmailSender
from tests.conftest import user_row


async def test_digest_email_carries_both_unsubscribe_ways(session):
    user = user_row()
    session.add(user)
    await session.flush()
    sent = []

    async def transport(msg):
        sent.append(msg)
    await EmailSender(session, "jobs@example.com", transport).send(user.id, "Your top matches")
    token = make_unsubscribe_token(str(user.id))
    [msg] = sent
    assert msg["List-Unsubscribe"] == f"<https://jobmatch.bbenard.dev/api/email/unsubscribe?token={token}>"
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"https://jobmatch.bbenard.dev/unsubscribe#{token}" in msg.get_content()


async def test_one_click_post_unsubscribes_and_the_digest_skips_them(client, session):
    user = user_row()
    job = Job(title="Backend Engineer")
    resume = Resume(user=user)
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.9, detail={}))
    await session.commit()
    token = make_unsubscribe_token(str(user.id))

    r = await client.post(f"/email/unsubscribe?token={token}", content="List-Unsubscribe=One-Click",
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 204
    await session.refresh(user)
    assert user.digest_opt_out_at is not None

    class Sender:
        sent = []
        async def send(self, user_id, body):
            self.sent.append(user_id)
    assert await send_weekly(session, Sender(), datetime.now(timezone.utc)) == 0


async def test_the_page_can_unsubscribe_and_resubscribe(client, session):
    user = user_row()
    session.add(user)
    await session.commit()
    token = make_unsubscribe_token(str(user.id))
    assert (await client.post("/email/unsubscribe", json={"token": token})).status_code == 204
    assert (await client.post("/email/unsubscribe", json={"token": token})).status_code == 204   # twice is fine
    assert (await client.post("/email/resubscribe", json={"token": token})).status_code == 204
    await session.refresh(user)
    assert user.digest_opt_out_at is None


async def test_bad_tokens_and_gets_change_nothing(client, session):
    user = user_row()
    session.add(user)
    await session.commit()
    good = make_unsubscribe_token(str(user.id))
    for bad in ("", "garbage", good[:-1] + ("0" if good[-1] != "0" else "1"),
                make_reset_token(str(user.id), user.hashed_password), f"not-a-uuid.{'0' * 64}"):
        assert (await client.post("/email/unsubscribe", json={"token": bad})).status_code == 400, bad
    assert (await client.get(f"/email/unsubscribe?token={good}")).status_code == 405       # scanners can't
    await session.refresh(user)
    assert user.digest_opt_out_at is None
