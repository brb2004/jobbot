from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.services import preferences_services as prefs_service
from app.services.preferences_services import Preferences

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/preferences", response_model=Preferences)
async def get_preferences(s=Depends(get_session), user_id=Depends(get_current_user)):
    prefs = await prefs_service.get_for(s, user_id)
    if prefs is None:
        raise HTTPException(401, "Not authenticated")
    return prefs


@router.put("/preferences", response_model=Preferences)
async def put_preferences(body: Preferences, s=Depends(get_session), user_id=Depends(get_current_user)):
    prefs = await prefs_service.save_for(s, user_id, body)
    if prefs is None:
        raise HTTPException(401, "Not authenticated")
    return prefs
