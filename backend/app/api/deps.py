import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})

async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if creds is None:
        raise UNAUTHORIZED
    try:
        decode_token(creds.credentials)
    except jwt.InvalidTokenError:
        raise UNAUTHORIZED