"""Forgot / reset password."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.api import limits_api as limits
from app.api.deps_api import client_ip, get_mailer
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.schemas.auth_schemas import ForgotIn, ResetIn
from app.services import auth_services
from app.services.email_services import reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

FORGOT_REPLY = {"detail": "If that account exists, we sent a reset link."}


@router.post("/forgot", status_code=202)
async def forgot(
    body: ForgotIn, request: Request, tasks: BackgroundTasks, s=Depends(get_session), send=Depends(get_mailer)
):
    """Same answer whether or not the account exists, or the per-address limit was hit."""
    ip = client_ip(request)
    if wait := limits.FORGOT_IP.blocked(ip):
        raise limits.too_many(wait, "Too many reset requests. Try again later.")
    limits.FORGOT_IP.hit(ip)
    email = body.email.lower()
    if limits.FORGOT_EMAIL.blocked(email):
        return FORGOT_REPLY
    limits.FORGOT_EMAIL.hit(email)
    if found := await auth_services.reset_link_token(s, email):
        user, token = found
        st = get_settings()
        # The token rides after '#', which browsers never send to a server, so it stays out of logs.
        # The link is built from APP_URL, never the Host header, so a forged Host can't redirect it.
        tasks.add_task(send, reset_email(st.EMAIL_FROM, user.email, f"{st.APP_URL}/reset#{token}"))
    return FORGOT_REPLY


@router.post("/reset", status_code=204)
async def reset(body: ResetIn, s=Depends(get_session)):
    if not await auth_services.reset_password(s, body.token, body.password):
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
