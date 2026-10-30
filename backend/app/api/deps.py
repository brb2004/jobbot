import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})

async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
    if creds is None:
        raise UNAUTHORIZED
    try:
        return UUID(decode_token(creds.credentials)["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UNAUTHORIZED