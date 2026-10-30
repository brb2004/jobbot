from app.db.models_db import Job
from app.services import prefilter_services as prefilter


def job(title, description):
    return Job(title=title, description=description)


def test_ranks_jobs_by_overlap_with_resume():
    resume = "Python FastAPI Postgres Kubernetes"
    jobs = [
        job("Sales", "cold calling and quotas"),
        job("Backend", "Python FastAPI Postgres"),
        job("DevOps", "Kubernetes and Terraform"),
    ]

    picked = prefilter.top_k(resume, jobs, k=2)

    assert [j.title for j in picked] == ["Backend", "DevOps"]


def test_drops_jobs_with_zero_overlap():
    picked = prefilter.top_k("Python", [job("Sales", "cold calling")], k=5)
    assert picked == []
def test_focused_job_beats_long_generic_job():
    resume = "python fastapi postgres"
    focused = job("Backend", "python fastapi postgres")
    generic = job("Staff", "python fastapi postgres " + " ".join(f"word{i}" for i in range(200)))

    assert prefilter.top_k(resume, [generic, focused], k=1) == [focused]