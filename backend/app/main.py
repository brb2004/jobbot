from fastapi import Depends, FastAPI
from app.api.routes import preferences_routes, auth_routes, jobs_routes, matches_routes, resumes_routes, places_routes, skills_routes, applications_routes, feedback_routes
from app.api.deps_api import require_verified

from app.core.config_core import get_settings  # noqa: E402


def docs_kwargs(enabled: bool) -> dict:
    return {} if enabled else {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(**docs_kwargs(get_settings().DOCS_ENABLED), )
app.include_router(preferences_routes.router)
app.include_router(auth_routes.router)
app.include_router(jobs_routes.router)
app.include_router(skills_routes.router)        # public: skill names for autocomplete
app.include_router(places_routes.router)        # public: place names for the pickers
app.include_router(matches_routes.router, dependencies=[Depends(require_verified)])   # confirmed emails only
app.include_router(resumes_routes.router, dependencies=[Depends(require_verified)])
app.include_router(applications_routes.router, dependencies=[Depends(require_verified)])
app.include_router(feedback_routes.router, dependencies=[Depends(require_verified)])

from fastapi import Request  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402


import re as _re  # noqa: E402


def _plain(msg: str) -> str:
    """Pydantic wording -> plain English."""
    msg = msg.removeprefix("Value error, ")
    msg = _re.sub(r"^String should have at least (\d+) characters?$", r"must be at least \1 characters", msg)
    msg = _re.sub(r"^String should have at most (\d+) characters?$", r"must be at most \1 characters", msg)
    msg = _re.sub(r"^value is not a valid email address.*$", "isn't a valid email address", msg)
    return msg


@app.exception_handler(RequestValidationError)
async def validation_error_without_echo(request: Request, exc: RequestValidationError):
    """Same 422 shape, minus 'input'/'ctx': never send a submitted value (like a password) back."""
    errors = [{**{k: v for k, v in e.items() if k not in ("input", "ctx")}, "msg": _plain(e["msg"])} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


from app.services.resumes_services import Unreadable  # noqa: E402


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
    h["Cache-Control"] = "no-store"                       # API responses are personal; never cache them
    if not request.url.path.startswith(("/docs", "/redoc")):   # Swagger needs its CDN scripts
        h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response



@app.get("/health", include_in_schema=False)
async def health():
    """Liveness for Docker/Kubernetes. No auth, no DB: 'the process is up and serving'."""
    return {"ok": True}
