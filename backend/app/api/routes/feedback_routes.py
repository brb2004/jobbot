from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api import limits_api as limits
from app.api.deps_api import client_ip, get_current_user, get_mailer
from app.core.db_core import get_session, get_sessionmaker
from app.schemas.feedback_schemas import FeedbackIn
from app.services import feedback_services as feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=202)
async def report(
    body: FeedbackIn,
    request: Request,
    tasks: BackgroundTasks,
    s=Depends(get_session),
    user_id=Depends(get_current_user),
    send=Depends(get_mailer),
    maker=Depends(get_sessionmaker),
):
    keys = ((limits.FEEDBACK_IP, client_ip(request)), (limits.FEEDBACK_USER, str(user_id)))
    for limiter, key in keys:
        if wait := limiter.blocked(key):
            raise limits.too_many(wait, "You've sent a lot of reports this hour. Try again later.")
    for limiter, key in keys:
        limiter.hit(key)
    agent = (request.headers.get("user-agent") or "")[:300] or None
    fid = await feedback.submit(s, user_id, body.kind, body.message.strip(), body.page, agent)
    tasks.add_task(feedback.acknowledge_now, maker, send, fid)  # after the response; the cron retries
    return {"ref": feedback.ref_of(fid), "detail": "Thanks. We've emailed you a confirmation."}
