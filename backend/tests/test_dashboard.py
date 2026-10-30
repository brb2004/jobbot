async def test_dashboard_includes_met_and_missing(client, session):
    me = uuid4()
    job, resume = Job(title="Backend"), Resume(user_id=me)
    session.add_all([job, resume])
    await session.flush()
    session.add(MatchScore(resume_id=resume.id, job_id=job.id, score=0.5,
                           detail={"met": ["Python"], "missing": ["Go"]}))
    await session.commit()

    r = await client.get("/dashboard", headers={"Authorization": f"Bearer {create_access_token(str(me))}"})

    assert r.json()[0]["detail"] == {"met": ["Python"], "missing": ["Go"]}