import asyncio
import re

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps_api import require_verified
from app.api.routes import (
    account_routes,
    applications_routes,
    auth_routes,
    email_routes,
    feedback_routes,
    jobs_routes,
    matches_routes,
    password_routes,
    places_routes,
    preferences_routes,
    resumes_routes,
    skills_routes,
    verify_routes,
)
from app.core.config_core import get_settings
from app.core.db_core import get_session
from app.services.resumes_services import Unreadable


def docs_kwargs(enabled: bool) -> dict:
    return {} if enabled else {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(
    **docs_kwargs(get_settings().DOCS_ENABLED),
)
app.include_router(preferences_routes.router)
app.include_router(auth_routes.router)
app.include_router(account_routes.router)
app.include_router(account_routes.account)  # DELETE /me
app.include_router(password_routes.router)
app.include_router(verify_routes.router)
app.include_router(email_routes.router)  # public: unsubscribe links carry a signed token
app.include_router(jobs_routes.router)
app.include_router(skills_routes.router)  # public: skill names for autocomplete
app.include_router(places_routes.router)  # public: place names for the pickers
app.include_router(matches_routes.router, dependencies=[Depends(require_verified)])  # confirmed emails only
app.include_router(resumes_routes.router, dependencies=[Depends(require_verified)])
app.include_router(applications_routes.router, dependencies=[Depends(require_verified)])
app.include_router(feedback_routes.router, dependencies=[Depends(require_verified)])


def _plain(msg: str) -> str:
    msg = msg.removeprefix("Value error, ")
    msg = re.sub(r"^String should have at least (\d+) characters?$", r"must be at least \1 characters", msg)
    msg = re.sub(r"^String should have at most (\d+) characters?$", r"must be at most \1 characters", msg)
    msg = re.sub(r"^value is not a valid email address.*$", "isn't a valid email address", msg)
    return msg


@app.exception_handler(RequestValidationError)
async def validation_error_without_echo(request: Request, exc: RequestValidationError):
    errors = [
        {**{k: v for k, v in e.items() if k not in ("input", "ctx")}, "msg": _plain(e["msg"])}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@app.exception_handler(Unreadable)
async def unreadable_resume(request: Request, exc: Unreadable):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Cache-Control"] = "no-store"  # API responses are personal; never cache them
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger needs its CDN scripts
        h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.get("/health", include_in_schema=False)
async def health():
    return {"ok": True}


@app.get("/ready", include_in_schema=False)
async def ready(s=Depends(get_session)):
    try:
        await asyncio.wait_for(s.execute(text("SELECT 1")), timeout=3)
    except Exception:
        return JSONResponse({"ok": False, "db": False}, status_code=503)
    return {"ok": True, "db": True}
