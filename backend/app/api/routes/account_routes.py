from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps_api import get_current_user
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.schemas.auth_schemas import UserOut
from app.services import auth_services

router = APIRouter(prefix="/auth", tags=["auth"])
account = APIRouter(prefix="/me", tags=["me"])


@router.get("/me", response_model=UserOut)
async def me(s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_services.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response, s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_services.get(s, user_id)
    user.tokens_valid_after = datetime.now(UTC)  # revokes every token issued before now
    await s.commit()
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")


@account.delete("", status_code=204)
async def delete_me(response: Response, s=Depends(get_session), user_id=Depends(get_current_user)):
    await auth_services.delete_account(s, user_id)
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")
