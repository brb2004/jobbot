async def test_upload_resume_then_list_it(client, auth_headers):
    files = {"file": ("resume.txt", b"Python, FastAPI, Postgres, Kubernetes", "text/plain")}

    up = await client.post("/resumes", files=files, headers=auth_headers)
    assert up.status_code == 201

    listed = await client.get("/resumes", headers=auth_headers)
    assert [r["filename"] for r in listed.json()] == ["resume.txt"]