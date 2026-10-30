from fastapi import APIRouter, Depends
from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.matches_schemas import MatchOut
from app.services import matches_services as matches_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("", response_model=list[MatchOut])
async def dashboard(s=Depends(get_session), user_id=Depends(get_current_user)):
    return await matches_service.for_user(s, user_id)