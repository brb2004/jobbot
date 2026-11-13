from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.api import limits_api as limits
from app.api.deps_api import get_current_user, get_mailer, set_session_cookie
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.core.security_core import make_verify_token
from app.schemas.auth_schemas import VerifyIn
from app.services import auth_services
from app.services.email_services import verify_email

router = APIRouter(prefix="/auth/verify", tags=["auth"])


def queue_verify(tasks: BackgroundTasks, send, user) -> None:
    st = get_settings()
    link = f"{st.APP_URL}/verify#{make_verify_token(str(user.id), user.email)}"
    tasks.add_task(send, verify_email(st.EMAIL_FROM, user.email, link))


@router.post("", status_code=204)
async def verify(body: VerifyIn, response: Response, s=Depends(get_session)):
    confirmed = await auth_services.confirm_email(s, body.token)
    if confirmed is None:
        raise HTTPException(
            400, "This confirmation link is invalid or has expired. Log in and send a new one."
        )
    user, first_time = confirmed
    if first_time:
        set_session_cookie(response, user.id)


@router.post("/resend", status_code=202)
async def resend(
    tasks: BackgroundTasks,
    s=Depends(get_session),
    user_id=Depends(get_current_user),
    send=Depends(get_mailer),
):
    user = await auth_services.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    if user.email_verified_at is None and not limits.VERIFY_RESEND.blocked(str(user.id)):
        limits.VERIFY_RESEND.hit(str(user.id))
        queue_verify(tasks, send, user)
    return {"detail": "If your email isn't confirmed yet, a new link is on its way."}
