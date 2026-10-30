from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.core.db import get_session
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}")
async def get_job(job_id: UUID, s=Depends(get_session), user=Depends(get_current_user)):
    job = await jobs_service.get(s, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {"id": str(job.id), "title": job.title}