import asyncio
import math
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from app.api.deps_api import client_ip, get_current_user
from app.core.db_core import get_session
from app.core.config_core import get_settings
from app.core.ratelimit_core import RateLimiter
from app.core.security_core import create_access_token
from app.schemas.auth_schemas import ForgotIn, LoginIn, RegisterIn, ResetIn, TokenOut, UserOut
from app.services import auth_services as auth_service
from app.services.email_services import reset_email, smtp_transport

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_FAILS = RateLimiter(max_hits=5, window_s=900)    # per (ip, email): stops guessing one account
LOGIN_IP = RateLimiter(max_hits=30, window_s=900)      # per ip: tarpit only, never a hard block (shared NAT)
REGISTER_IP = RateLimiter(max_hits=5, window_s=3600)   # per ip: new accounts per hour
FORGOT_IP = RateLimiter(max_hits=10, window_s=3600)    # per ip: reset requests per hour
FORGOT_EMAIL = RateLimiter(max_hits=3, window_s=3600)  # per address: nobody can mail-bomb an inbox
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
    ip = client_ip(request)
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
    ip = client_ip(request)   # behind a reverse proxy: run uvicorn --proxy-headers
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


def get_mailer():
    """Overridden in tests to capture messages instead of sending them."""
    st = get_settings()
    return smtp_transport(st.SMTP_HOST, st.SMTP_PORT, st.SMTP_USER, st.SMTP_PASSWORD)


FORGOT_REPLY = {"detail": "If that account exists, we sent a reset link."}


@router.post("/forgot", status_code=202)
async def forgot(body: ForgotIn, request: Request, tasks: BackgroundTasks,
                 s=Depends(get_session), send=Depends(get_mailer)):
    ip = client_ip(request)
    if wait := FORGOT_IP.blocked(ip):
        raise HTTPException(429, "Too many reset requests. Try again later.",
                            headers={"Retry-After": str(math.ceil(wait))})
    FORGOT_IP.hit(ip)
    email = body.email.lower()
    if FORGOT_EMAIL.blocked(email):
        return FORGOT_REPLY                                    # same answer: the limit isn't revealed either
    FORGOT_EMAIL.hit(email)
    if found := await auth_service.reset_link_token(s, email):
        user, token = found
        st = get_settings()
        # After '#': browsers never send the fragment to a server, so the token stays out of proxy logs.
        # APP_URL, not the Host header: a forged Host can't aim the emailed link at an attacker's site.
        tasks.add_task(send, reset_email(st.EMAIL_FROM, user.email, f"{st.APP_URL}/reset#{token}"))
    return FORGOT_REPLY                                        # mail goes out after the response: same speed either way


@router.post("/reset", status_code=204)
async def reset(body: ResetIn, s=Depends(get_session)):
    if not await auth_service.reset_password(s, body.token, body.password):
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
