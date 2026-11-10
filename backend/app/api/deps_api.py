from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.core.security_core import decode_token
from app.db.models_db import User

bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(request: Request,
                           creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                           s: AsyncSession = Depends(get_session)) -> UUID:
    """Scripts send 'Authorization: Bearer'; the browser sends the httpOnly cookie. Either works,
    unless the user logged out (or was deleted) after the token was issued."""
    token = creds.credentials if creds else request.cookies.get(get_settings().COOKIE_NAME)
    if not token:
        raise UNAUTHORIZED
    try:
        claims = decode_token(token)
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UNAUTHORIZED
    user = await s.get(User, user_id)
    if user is None:
        raise UNAUTHORIZED                                              # account deleted
    cutoff = user.tokens_valid_after
    if cutoff is not None and claims.get("iat", 0) < cutoff.timestamp():
        raise UNAUTHORIZED                                              # logged out after this token was issued
    return user_id


def client_ip(request: Request) -> str:
    """Real visitor IP for rate limits. Cloudflare overwrites CF-Connecting-IP, so it can't be forged,
    but only trust it when every request comes through Cloudflare. Never X-Forwarded-For (client-controlled)."""
    if get_settings().TRUST_CF_CONNECTING_IP and (ip := request.headers.get("cf-connecting-ip")):
        return ip
    return request.client.host if request.client else "unknown"


NOT_CONFIRMED = HTTPException(403, "Confirm your email first. Check your inbox for the link.")


async def require_verified(user_id: UUID = Depends(get_current_user),
                           s: AsyncSession = Depends(get_session)) -> UUID:
    """Gate for resume and match endpoints. The row is already in the session's identity map
    (get_current_user loaded it), so this costs no extra query."""
    user = await s.get(User, user_id)
    if user.email_verified_at is None:
        raise NOT_CONFIRMED
    return user_id
