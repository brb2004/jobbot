from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.applications_schemas import ApplicationOut
from app.services import applications_services as applications

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
async def list_applied(s=Depends(get_session), user_id=Depends(get_current_user)):
    return await applications.list_for(s, user_id)


@router.put("/{job_id}", status_code=204)            # PUT: marking twice is the same as once
async def mark_applied(job_id: UUID, status: Literal["applied", "dismissed"] = "applied",
                       s=Depends(get_session), user_id=Depends(get_current_user)):
    if not await applications.mark(s, user_id, job_id, status):
        raise HTTPException(404, "No such job")


@router.delete("/{job_id}", status_code=204)
async def undo_applied(job_id: UUID, s=Depends(get_session), user_id=Depends(get_current_user)):
    await applications.undo(s, user_id, job_id)
