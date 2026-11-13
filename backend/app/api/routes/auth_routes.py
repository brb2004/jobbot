import asyncio
import math
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from app.api.deps_api import client_ip, get_current_user, set_session_cookie
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.core.ratelimit_core import RateLimiter
from app.core.security_core import make_verify_token
from app.schemas.auth_schemas import ForgotIn, LoginIn, RegisterIn, ResetIn, TokenOut, UserOut, VerifyIn
from app.services import auth_services as auth_service
from app.services.email_services import account_exists_email, reset_email, smtp_transport, verify_email

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_FAILS = RateLimiter(max_hits=5, window_s=900)  # per (ip, email): stops guessing one account
LOGIN_IP = RateLimiter(max_hits=30, window_s=900)  # per ip: tarpit only, never a hard block (shared NAT)
LOGIN_EMAIL = RateLimiter(
    max_hits=10**9, window_s=900
)  # per account, any ip: counts failures for the slowdown
REGISTER_IP = RateLimiter(max_hits=5, window_s=3600)  # per ip: new accounts per hour
FORGOT_IP = RateLimiter(max_hits=10, window_s=3600)  # per ip: reset requests per hour
VERIFY_RESEND = RateLimiter(max_hits=3, window_s=3600)  # per user: confirmation re-sends
FORGOT_EMAIL = RateLimiter(max_hits=3, window_s=3600)  # per address: nobody can mail-bomb an inbox
SIGNUP_EMAIL = RateLimiter(max_hits=3, window_s=3600)  # per address: "you already have an account" mails
TARPIT_S = 2.0  # delay for a noisy ip; asyncio.sleep doesn't block others
EMAIL_FREE_FAILS = 5  # per-account failures before the slowdown starts
EMAIL_DELAY_S, EMAIL_DELAY_MAX_S = 1.0, 16.0  # then 1, 2, 4, 8, 16, 16... seconds per attempt


def account_delay(fails: int) -> float:
    """Guessing one account from many ips gets slower and slower, but the right password always
    works: a lockout would let anyone lock anyone else out."""
    if fails < EMAIL_FREE_FAILS:
        return 0.0
    return min(EMAIL_DELAY_MAX_S, EMAIL_DELAY_S * 2 ** (fails - EMAIL_FREE_FAILS))


def get_mailer():
    """Overridden in tests to capture messages instead of sending them."""
    st = get_settings()
    return smtp_transport(st.SMTP_HOST, st.SMTP_PORT, st.SMTP_USER, st.SMTP_PASSWORD, st.EMAIL_REPLY_TO)


def _queue_verify(tasks: BackgroundTasks, send, user) -> None:
    st = get_settings()
    link = f"{st.APP_URL}/verify#{make_verify_token(str(user.id), user.email)}"
    tasks.add_task(send, verify_email(st.EMAIL_FROM, user.email, link))


def _start_session(response: Response, user_id, include_token: bool = False) -> TokenOut:
    token = set_session_cookie(response, user_id)
    return TokenOut(access_token=token if include_token else None)  # body token only when a script asks


REGISTER_REPLY = {"detail": "Check your email to finish signing up."}


@router.post("/register", status_code=202)
async def register(
    body: RegisterIn,
    request: Request,
    tasks: BackgroundTasks,
    s=Depends(get_session),
    send=Depends(get_mailer),
):
    """Same answer, same speed, same rate limit whether or not the address has an account (no 409):
    a new address gets a confirmation link, a registered one gets "you already have an account".
    No session here; the confirmation link logs you in (or log in with your password)."""
    ip = client_ip(request)
    if wait := REGISTER_IP.blocked(ip):
        raise HTTPException(
            429,
            "Too many sign-ups from this network. Try again later.",
            headers={"Retry-After": str(math.ceil(wait))},
        )
    REGISTER_IP.hit(ip)  # every attempt counts: existing or not
    email = body.email.lower()
    try:
        user = await auth_service.register(s, email, body.password)  # hashes first: both paths pay bcrypt
    except auth_service.EmailTaken:
        user = await auth_service.by_email(s, email)
        if user is not None and not SIGNUP_EMAIL.blocked(email):
            SIGNUP_EMAIL.hit(email)
            if user.email_verified_at is None:
                _queue_verify(tasks, send, user)  # never confirmed: a fresh link is what they need
            else:
                tasks.add_task(
                    send, account_exists_email(get_settings().EMAIL_FROM, user.email, get_settings().APP_URL)
                )
        return REGISTER_REPLY
    _queue_verify(tasks, send, user)  # digests wait until this is clicked
    return REGISTER_REPLY


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn, request: Request, response: Response, token: bool = False, s=Depends(get_session)
):
    ip = client_ip(request)  # behind a reverse proxy: run uvicorn --proxy-headers
    email = body.email.lower()
    keys = [(LOGIN_FAILS, f"{ip}|{email}"), (LOGIN_IP, ip), (LOGIN_EMAIL, email)]
    wait = LOGIN_FAILS.blocked(keys[0][1])  # hard block: this ip guessing this account
    if LOGIN_IP.blocked(ip):
        await asyncio.sleep(TARPIT_S)  # noisy ip: slow down, never lock out a right password
    if wait:
        raise HTTPException(
            429, "Too many attempts. Try again later.", headers={"Retry-After": str(math.ceil(wait))}
        )
    if delay := account_delay(LOGIN_EMAIL.count(email)):
        await asyncio.sleep(delay)  # this account is being guessed from many ips
    user = await auth_service.authenticate(s, body.email, body.password)
    if user is None:
        for limiter, k in keys:
            limiter.hit(k)  # count failures only
        raise HTTPException(401, "Invalid email or password")  # one message for both cases
    LOGIN_FAILS.reset(keys[0][1])  # success clears this ip+email
    LOGIN_EMAIL.reset(email)  # and the account's slowdown
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
    user.tokens_valid_after = datetime.now(UTC)  # every token issued before now stops working
    await s.commit()
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")  # JS can't delete an httpOnly cookie


FORGOT_REPLY = {"detail": "If that account exists, we sent a reset link."}


@router.post("/forgot", status_code=202)
async def forgot(
    body: ForgotIn, request: Request, tasks: BackgroundTasks, s=Depends(get_session), send=Depends(get_mailer)
):
    ip = client_ip(request)
    if wait := FORGOT_IP.blocked(ip):
        raise HTTPException(
            429, "Too many reset requests. Try again later.", headers={"Retry-After": str(math.ceil(wait))}
        )
    FORGOT_IP.hit(ip)
    email = body.email.lower()
    if FORGOT_EMAIL.blocked(email):
        return FORGOT_REPLY  # same answer: the limit isn't revealed either
    FORGOT_EMAIL.hit(email)
    if found := await auth_service.reset_link_token(s, email):
        user, token = found
        st = get_settings()
        # After '#': browsers never send the fragment to a server, so the token stays out of proxy logs.
        # APP_URL, not the Host header: a forged Host can't aim the emailed link at an attacker's site.
        tasks.add_task(send, reset_email(st.EMAIL_FROM, user.email, f"{st.APP_URL}/reset#{token}"))
    return FORGOT_REPLY  # mail goes out after the response: same speed either way


@router.post("/reset", status_code=204)
async def reset(body: ResetIn, s=Depends(get_session)):
    if not await auth_service.reset_password(s, body.token, body.password):
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")


@router.post("/verify", status_code=204)
async def verify(body: VerifyIn, response: Response, s=Depends(get_session)):
    """The click that confirms the address also logs that browser in, so sign-up -> link -> matches
    needs no second password entry. Clicking an old link again only confirms; it never logs in."""
    confirmed = await auth_service.confirm_email(s, body.token)
    if confirmed is None:
        raise HTTPException(
            400, "This confirmation link is invalid or has expired. Log in and send a new one."
        )
    user, first_time = confirmed
    if first_time:
        set_session_cookie(response, user.id)


@router.post("/verify/resend", status_code=202)
async def resend_verification(
    tasks: BackgroundTasks,
    s=Depends(get_session),
    user_id=Depends(get_current_user),
    send=Depends(get_mailer),
):
    user = await auth_service.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    if user.email_verified_at is None and not VERIFY_RESEND.blocked(str(user.id)):
        VERIFY_RESEND.hit(str(user.id))
        _queue_verify(tasks, send, user)
    return {"detail": "If your email isn't confirmed yet, a new link is on its way."}


account = APIRouter(prefix="/me", tags=["me"])


@account.delete("", status_code=204)
async def delete_me(response: Response, s=Depends(get_session), user_id=Depends(get_current_user)):
    """Delete my account, resume and matches. Can't be undone."""
    await auth_service.delete_account(s, user_id)
    response.delete_cookie(get_settings().COOKIE_NAME, path="/")
