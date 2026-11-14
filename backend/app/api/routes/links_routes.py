from fastapi import APIRouter, Depends, HTTPException

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.services import links_services
from app.services.links_services import Links

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/links", response_model=Links)
async def get_links(s=Depends(get_session), user_id=Depends(get_current_user)):
    links = await links_services.get_for(s, user_id)
    if links is None:
        raise HTTPException(401, "Not authenticated")
    return links


@router.put("/links", response_model=Links)
async def put_links(body: Links, s=Depends(get_session), user_id=Depends(get_current_user)):
    links = await links_services.save_for(s, user_id, body)
    if links is None:
        raise HTTPException(401, "Not authenticated")
    return links
