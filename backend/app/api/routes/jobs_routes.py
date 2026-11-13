from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.jobs_schemas import JobOut
from app.services import jobs_services as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    s=Depends(get_session),
    user=Depends(get_current_user),
):
    return await jobs_service.list_open(s, limit, offset)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UUID, s=Depends(get_session), user=Depends(get_current_user)):
    job = await jobs_service.get(s, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job
