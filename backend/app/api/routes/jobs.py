from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.core.db import get_session
from app.services import jobs as jobs_service
from app.schemas.jobs import JobOut
router = APIRouter(prefix="/jobs", tags=["jobs"])



@router.get("", response_model=list[JobOut])
async def list_jobs(s=Depends(get_session), user=Depends(get_current_user)):
    return await jobs_service.list_all(s)

@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: UUID, s=Depends(get_session), user=Depends(get_current_user)):
    job = await jobs_service.get(s, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job
