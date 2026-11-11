import math

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.api.deps_api import client_ip, get_current_user
from app.api.routes.auth_routes import get_mailer
from app.core.db_core import get_session, get_sessionmaker
from app.core.ratelimit_core import RateLimiter
from app.schemas.feedback_schemas import FeedbackIn
from app.services import feedback_services as feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

FEEDBACK_USER = RateLimiter(max_hits=5, window_s=3600)   # per account: reports per hour
FEEDBACK_IP = RateLimiter(max_hits=20, window_s=3600)    # per ip: stops one machine cycling accounts


@router.post("", status_code=202)
async def report(body: FeedbackIn, request: Request, tasks: BackgroundTasks, s=Depends(get_session),
                 user_id=Depends(get_current_user), send=Depends(get_mailer), maker=Depends(get_sessionmaker)):
    keys = ((FEEDBACK_IP, client_ip(request)), (FEEDBACK_USER, str(user_id)))
    for limiter, key in keys:
        if wait := limiter.blocked(key):
            raise HTTPException(429, "You've sent a lot of reports this hour. Try again later.",
                                headers={"Retry-After": str(math.ceil(wait))})
    for limiter, key in keys:
        limiter.hit(key)
    fid = await feedback.submit(s, user_id, body.kind, body.message.strip(), body.page,
                                (request.headers.get("user-agent") or "")[:300] or None)
    tasks.add_task(feedback.acknowledge_now, maker, send, fid)   # after the response; the CronJob retries failures
    return {"ref": feedback.ref_of(fid), "detail": "Thanks. We've emailed you a confirmation."}
