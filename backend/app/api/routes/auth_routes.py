import asyncio
import math
from datetime import datetime, timezone

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
LOGIN_IP = RateLimiter(max_hits=30, window_s=900)      # per ip: tarpit only, never a hard block (shared NAT)
REGISTER_IP = RateLimiter(max_hits=5, window_s=3600)   # per ip: new accounts per hour
TARPIT_S = 2.0                                         # delay for a noisy ip; asyncio.sleep doesn't block others


def _start_session(response: Response, user_id, include_token: bool = False) -> TokenOut:
    """httpOnly: page JS can't read it. SameSite=Lax: not sent on cross-site POST/PUT (CSRF)."""
    s = get_settings()
    token = create_access_token(str(user_id))
    response.set_cookie(s.COOKIE_NAME, token, max_age=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        httponly=True, secure=s.COOKIE_SECURE, samesite="lax", path="/")
    return TokenOut(access_token=token if include_token else None)   # body token only when a script asks


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, request: Request, response: Response, token: bool = False,
                   s=Depends(get_session)):
    ip = request.client.host if request.client else "unknown"
    if wait := REGISTER_IP.blocked(ip):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.",
                            headers={"Retry-After": str(math.ceil(wait))})
    try:
        user = await auth_service.register(s, body.email, body.password)
    except auth_service.EmailTaken:
        raise HTTPException(409, "Email already registered")
    REGISTER_IP.hit(ip)                                          # count accounts created per ip
    return _start_session(response, user.id, token)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response, token: bool = False,
                s=Depends(get_session)):
    ip = request.client.host if request.client else "unknown"   # behind a reverse proxy: run uvicorn --proxy-headers
    keys = [(LOGIN_FAILS, f"{ip}|{body.email.lower()}"), (LOGIN_IP, ip)]
    wait = LOGIN_FAILS.blocked(keys[0][1])                       # hard block: this ip guessing this account
    if LOGIN_IP.blocked(ip):
        await asyncio.sleep(TARPIT_S)                            # noisy ip: slow down, never lock out a right password
    if wait:
        raise HTTPException(429, "Too many attempts. Try again later.", headers={"Retry-After": str(math.ceil(wait))})
    user = await auth_service.authenticate(s, body.email, body.password)
    if user is None:
        for limiter, k in keys:
            limiter.hit(k)                                       # count failures only
        raise HTTPException(401, "Invalid email or password")    # one message for both cases
    LOGIN_FAILS.reset(keys[0][1])                                # success clears this ip+email
    return _start_session(response, user.id, token)


@router.get("/me", response_model=UserOut)
async def me(s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_service.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response, s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_service.get(s, user_id)
    user.tokens_valid_after = datetime.now(timezone.utc)           # every token issued before now stops working
    await s.commit()
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")      # JS can't delete an httpOnly cookie
