from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.schemas.matches_schemas import MatchOut
from app.services import matches_services
from app.services.seen_services import mark_seen, seen_ids

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=list[MatchOut])
async def dashboard(resume: UUID | None = None, s=Depends(get_session), user_id=Depends(get_current_user)):
    rows = await matches_services.for_user(s, user_id, resume)
    seen = await seen_ids(s, user_id, (r.job_id for r in rows))
    out = [
        MatchOut.model_validate(r, from_attributes=True).model_copy(update={"new": r.job_id not in seen})
        for r in rows
    ]
    await mark_seen(s, user_id, (r.job_id for r in rows))
    await s.commit()
    return out
