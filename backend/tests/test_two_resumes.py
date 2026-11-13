from sqlalchemy import select

from app.core.security_core import create_access_token
from app.db.models_db import Job, MatchScore, Resume
from app.schemas.matches_schemas import MatchOut
from app.services import digest_services as digest
from tests.test_resumes import _user


def h(uid):
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def up(client, uid, text, name=None, replace=None):
    url = "/resumes" + (f"?replace={replace}" if replace else "")
    return await client.post(
        url,
        headers=h(uid),
        data={"name": name} if name else {},
        files={"file": ("cv.txt", text.encode(), "text/plain")},
    )


def jobs():
    return [
        Job(
            title="Backend Engineer",
            board="b1",
            skills=["Python"],
            requirements=["Python"],
            url="https://x/1",
        ),
        Job(
            title="DevOps Engineer",
            board="b2",
            skills=["Kubernetes"],
            requirements=["Kubernetes"],
            url="https://x/2",
        ),
        Job(
            title="Platform Engineer",
            board="b3",
            skills=["Python", "Kubernetes"],
            requirements=["Python", "Kubernetes"],
            url="https://x/3",
        ),
    ]


async def test_two_resumes_then_a_third_is_refused(client, session):
    me = await _user(session)
    assert (await up(client, me, "Python developer", "Backend")).status_code == 201
    assert (await up(client, me, "Kubernetes operator", "DevOps")).status_code == 201
    r = await up(client, me, "Go developer")
    assert r.status_code == 409 and "replace or delete" in r.json()["detail"].lower()
    listed = (await client.get("/resumes", headers=h(me))).json()
    assert [x["name"] for x in listed] == ["Backend", "DevOps"]  # oldest first


async def test_each_resume_has_its_own_matches_and_titles(client, session):
    session.add_all(jobs())
    await session.flush()
    me = await _user(session)
    backend = (await up(client, me, "Python Kubernetes developer", "Backend")).json()
    devops = (await up(client, me, "Python Kubernetes operator", "DevOps")).json()
    r = await client.patch(
        f"/resumes/{devops['id']}", headers=h(me), json={"own": {"include_titles": ["devops", "platform"]}}
    )
    assert r.status_code == 200 and r.json()["own"]["include_titles"] == ["devops", "platform"]

    def titles(rid):
        return client.get(f"/dashboard?resume={rid}", headers=h(me))

    assert {m["title"] for m in (await titles(backend["id"])).json()} == {
        "Backend Engineer",
        "DevOps Engineer",
        "Platform Engineer",
    }  # account default: all engineering
    assert {m["title"] for m in (await titles(devops["id"])).json()} == {
        "DevOps Engineer",
        "Platform Engineer",
    }
    first = (await client.get("/dashboard", headers=h(me))).json()  # no ?resume: the first one
    assert len(first) == 3


async def test_replacing_keeps_name_and_settings(client, session):
    me = await _user(session)
    a = (await up(client, me, "Python developer", "Backend")).json()
    await client.patch(f"/resumes/{a['id']}", headers=h(me), json={"own": {"years_experience": 2}})
    b = (await up(client, me, "Python and Go developer", replace=a["id"])).json()
    assert b["id"] != a["id"] and b["name"] == "Backend" and b["own"]["years_experience"] == 2
    assert len((await client.get("/resumes", headers=h(me))).json()) == 1


async def test_someone_elses_resume_looks_missing(client, session):
    me, other = await _user(session), await _user(session)
    theirs = (await up(client, other, "Python developer", "Theirs")).json()
    assert (
        await client.patch(f"/resumes/{theirs['id']}", headers=h(me), json={"name": "x"})
    ).status_code == 404
    assert (await client.delete(f"/resumes/{theirs['id']}", headers=h(me))).status_code == 404
    assert (await up(client, me, "Go developer", replace=theirs["id"])).status_code == 404
    assert (await client.get(f"/dashboard?resume={theirs['id']}", headers=h(me))).json() == []


async def test_conflicting_own_titles_are_refused(client, session):
    me = await _user(session)
    a = (await up(client, me, "Python developer")).json()
    r = await client.patch(
        f"/resumes/{a['id']}",
        headers=h(me),
        json={"own": {"include_titles": ["devops"], "exclude_titles": ["devops"]}},
    )
    assert r.status_code == 422 and "both" in r.json()["detail"]


async def test_delete_removes_it_and_its_matches(client, session):
    session.add_all(jobs())
    await session.flush()
    me = await _user(session)
    a = (await up(client, me, "Python developer")).json()
    assert (
        await session.scalars(select(MatchScore).where(MatchScore.resume_id == a["id"]))
    ).all()  # had some
    assert (await client.delete(f"/resumes/{a['id']}", headers=h(me))).status_code == 204
    assert (await session.scalars(select(MatchScore).where(MatchScore.resume_id == a["id"]))).all() == []
    assert (await session.scalars(select(Resume).where(Resume.user_id == me))).all() == []


def test_weekly_email_has_a_section_per_resume_and_each_job_once():
    import uuid

    j1, j2, j3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [
        MatchOut(job_id=j1, title="Backend Engineer", score=0.9, resume="Backend"),
        MatchOut(job_id=j3, title="Platform Engineer", score=0.6, resume="Backend"),
        MatchOut(job_id=j2, title="DevOps Engineer", score=0.8, resume="DevOps"),
        MatchOut(job_id=j3, title="Platform Engineer", score=0.7, resume="DevOps"),
    ]
    text = digest.render(rows, top_n=20)
    assert text.index("== Backend ==") < text.index("== DevOps ==")
    assert text.count("Platform Engineer") == 1
    assert text.index("Platform Engineer") > text.index("== DevOps ==")  # under the resume it matched best
    one = digest.render(
        [MatchOut(job_id=j1, title="Backend Engineer", score=0.9, resume="Backend")], top_n=20
    )
    assert "==" not in one  # one resume: no headers
