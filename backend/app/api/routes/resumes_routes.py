from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.resumes_schemas import ResumeOut
from app.services import resumes_services as resumes_service

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=201)
async def upload(file: UploadFile = File(...), s=Depends(get_session), user_id=Depends(get_current_user)):
    data = await file.read(resumes_service.MAX_BYTES + 1)      # never read more than limit + 1
    try:
        return await resumes_service.upload(s, user_id, file.filename or "", data)
    except resumes_service.UnsupportedType:
        raise HTTPException(415, "Upload a .pdf, .docx, or .txt file")
    except resumes_service.TooLarge:
        raise HTTPException(413, "File must be 2 MB or smaller")


@router.get("", response_model=list[ResumeOut])
async def list_mine(s=Depends(get_session), user_id=Depends(get_current_user)):
    return await resumes_service.list_for(s, user_id)