from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.db_core import get_session
from app.core.security_core import unsubscribe_token_user
from app.db.models_db import User

router = APIRouter(prefix="/email", tags=["email"])
BAD_LINK = HTTPException(400, "This unsubscribe link isn't valid.")


class TokenIn(BaseModel):
    token: str


async def _user(s, token: str) -> User:
    claimed = unsubscribe_token_user(token)
    try:
        user = await s.get(User, UUID(claimed)) if claimed else None
    except ValueError:
        user = None
    if user is None:
        raise BAD_LINK
    return user


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(request: Request, token: str | None = None, s=Depends(get_session)):
    if token is None and request.headers.get("content-type", "").startswith("application/json"):
        try:
            token = TokenIn.model_validate(await request.json()).token
        except Exception:
            raise BAD_LINK from None
    user = await _user(s, token or "")
    if user.digest_opt_out_at is None:
        user.digest_opt_out_at = datetime.now(UTC)
        await s.commit()


@router.post("/resubscribe", status_code=204)
async def resubscribe(body: TokenIn, s=Depends(get_session)):
    user = await _user(s, body.token)
    user.digest_opt_out_at = None
    await s.commit()
