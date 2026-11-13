from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.resumes_schemas import ResumeOut, ResumeUpdate
from app.services import resumes_services as resumes_service

router = APIRouter(prefix="/resumes", tags=["resumes"])
NOT_FOUND = HTTPException(404, "Resume not found")


@router.post("", response_model=ResumeOut, status_code=201)
async def upload(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=40),
    replace: UUID | None = None,
    s=Depends(get_session),
    user_id=Depends(get_current_user),
):
    data = await file.read(resumes_service.MAX_BYTES + 1)  # never read more than limit + 1
    try:
        return await resumes_service.upload(s, user_id, file.filename or "", data, replace=replace, name=name)
    except resumes_service.UnsupportedType:
        raise HTTPException(415, "Upload a .pdf, .docx, or .txt file") from None
    except resumes_service.TooLarge:
        raise HTTPException(413, "File must be 2 MB or smaller") from None
    except resumes_service.TooMany:
        raise HTTPException(
            409, f"You can keep {resumes_service.MAX_RESUMES} resumes. Replace or delete one first."
        ) from None
    except resumes_service.NotFound:
        raise NOT_FOUND from None


@router.get("", response_model=list[ResumeOut])
async def list_mine(s=Depends(get_session), user_id=Depends(get_current_user)):
    return await resumes_service.list_for(s, user_id)


@router.patch("/{resume_id}", response_model=ResumeOut)
async def update(
    resume_id: UUID, body: ResumeUpdate, s=Depends(get_session), user_id=Depends(get_current_user)
):
    try:
        return await resumes_service.update(s, user_id, resume_id, body.name, body.own)
    except resumes_service.NotFound:
        raise NOT_FOUND from None
    except ValidationError as e:  # e.g. a title both included and excluded
        raise HTTPException(422, e.errors()[0]["msg"].removeprefix("Value error, ")) from None


@router.delete("/{resume_id}", status_code=204)
async def delete(resume_id: UUID, s=Depends(get_session), user_id=Depends(get_current_user)):
    try:
        await resumes_service.remove(s, user_id, resume_id)
    except resumes_service.NotFound:
        raise NOT_FOUND from None
