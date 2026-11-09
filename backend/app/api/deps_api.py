from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config_core import get_settings
from app.core.security_core import decode_token

bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(request: Request,
                           creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
    """Scripts send 'Authorization: Bearer'; the browser sends the httpOnly session cookie. Either works."""
    token = creds.credentials if creds else request.cookies.get(get_settings().COOKIE_NAME)
    if not token:
        raise UNAUTHORIZED
    try:
        return UUID(decode_token(token)["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UNAUTHORIZED
