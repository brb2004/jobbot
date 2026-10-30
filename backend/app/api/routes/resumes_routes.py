from fastapi import APIRouter, Depends, File, UploadFile
from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.resumes_schemas import ResumeOut
from app.services import resumes_services as resumes_service

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=201)
async def upload(file: UploadFile = File(...), s=Depends(get_session), user_id=Depends(get_current_user)):
    return await resumes_service.create(s, user_id, file.filename or "resume", await file.read())


@router.get("", response_model=list[ResumeOut])
async def list_mine(s=Depends(get_session), user_id=Depends(get_current_user)):
    return await resumes_service.list_for(s, user_id)