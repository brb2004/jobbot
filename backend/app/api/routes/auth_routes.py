import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from app.api import limits_api as limits
from app.api.deps_api import client_ip, get_mailer, set_session_cookie
from app.api.routes.verify_routes import queue_verify
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.schemas.auth_schemas import LoginIn, RegisterIn, TokenOut
from app.services import auth_services
from app.services.email_services import account_exists_email

router = APIRouter(prefix="/auth", tags=["auth"])

REGISTER_REPLY = {"detail": "Check your email to finish signing up."}


@router.post("/register", status_code=202)
async def register(
    body: RegisterIn,
    request: Request,
    tasks: BackgroundTasks,
    s=Depends(get_session),
    send=Depends(get_mailer),
):
    ip = client_ip(request)
    if wait := limits.REGISTER_IP.blocked(ip):
        raise limits.too_many(wait, "Too many sign-ups from this network. Try again later.")
    limits.REGISTER_IP.hit(ip)
    email = body.email.lower()
    try:
        user = await auth_services.register(s, email, body.password)
    except auth_services.EmailTaken:
        await _tell_existing(s, email, tasks, send)
    else:
        queue_verify(tasks, send, user)
    return REGISTER_REPLY


async def _tell_existing(s, email: str, tasks: BackgroundTasks, send) -> None:
    user = await auth_services.by_email(s, email)
    if user is None or limits.SIGNUP_EMAIL.blocked(email):
        return
    limits.SIGNUP_EMAIL.hit(email)
    if user.email_verified_at is None:
        queue_verify(tasks, send, user)  # never confirmed: a fresh link is what they need
    else:
        st = get_settings()
        tasks.add_task(send, account_exists_email(st.EMAIL_FROM, user.email, st.APP_URL))


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn, request: Request, response: Response, token: bool = False, s=Depends(get_session)
):
    ip, email = client_ip(request), body.email.lower()
    pair = f"{ip}|{email}"
    await _slow_down(ip, email, pair)
    user = await auth_services.authenticate(s, body.email, body.password)
    if user is None:
        for limiter, key in ((limits.LOGIN_FAILS, pair), (limits.LOGIN_IP, ip), (limits.LOGIN_EMAIL, email)):
            limiter.hit(key)
        raise HTTPException(401, "Invalid email or password")
    limits.LOGIN_FAILS.reset(pair)
    limits.LOGIN_EMAIL.reset(email)
    session_token = set_session_cookie(response, user.id)
    return TokenOut(access_token=session_token if token else None)  # body token only when a script asks


async def _slow_down(ip: str, email: str, pair: str) -> None:
    wait = limits.LOGIN_FAILS.blocked(pair)
    if limits.LOGIN_IP.blocked(ip):
        await asyncio.sleep(limits.TARPIT_S)
    if wait:
        raise limits.too_many(wait, "Too many attempts. Try again later.")
    if delay := limits.account_delay(limits.LOGIN_EMAIL.count(email)):
        await asyncio.sleep(delay)
