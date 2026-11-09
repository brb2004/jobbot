import math

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.core.config_core import get_settings
from app.core.ratelimit_core import RateLimiter
from app.core.security_core import create_access_token
from app.schemas.auth_schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth_services as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_FAILS = RateLimiter(max_hits=5, window_s=900)    # per (ip, email): stops guessing one account
LOGIN_IP = RateLimiter(max_hits=30, window_s=900)      # per ip: stops one machine spraying many accounts


def _start_session(response: Response, user_id) -> TokenOut:
    """httpOnly: page JS can't read it. SameSite=Lax: not sent on cross-site POST/PUT (CSRF)."""
    s = get_settings()
    token = create_access_token(str(user_id))
    response.set_cookie(s.COOKIE_NAME, token, max_age=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        httponly=True, secure=s.COOKIE_SECURE, samesite="lax", path="/")
    return TokenOut(access_token=token)      # still returned for scripts (dash.sh, curl)


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, response: Response, s=Depends(get_session)):
    try:
        user = await auth_service.register(s, body.email, body.password)
    except auth_service.EmailTaken:
        raise HTTPException(409, "Email already registered")
    return _start_session(response, user.id)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response, s=Depends(get_session)):
    ip = request.client.host if request.client else "unknown"   # behind a reverse proxy: run uvicorn --proxy-headers
    keys = [(LOGIN_FAILS, f"{ip}|{body.email.lower()}"), (LOGIN_IP, ip)]
    wait = max(limiter.blocked(k) for limiter, k in keys)
    if wait:
        raise HTTPException(429, "Too many attempts. Try again later.", headers={"Retry-After": str(math.ceil(wait))})
    user = await auth_service.authenticate(s, body.email, body.password)
    if user is None:
        for limiter, k in keys:
            limiter.hit(k)                                       # count failures only
        raise HTTPException(401, "Invalid email or password")    # one message for both cases
    LOGIN_FAILS.reset(keys[0][1])                                # success clears this ip+email
    return _start_session(response, user.id)


@router.get("/me", response_model=UserOut)
async def me(s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_service.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")      # JS can't delete an httpOnly cookie
