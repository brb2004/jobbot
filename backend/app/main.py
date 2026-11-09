from fastapi import FastAPI
from app.api.routes import preferences_routes, auth_routes, jobs_routes, matches_routes, resumes_routes

app = FastAPI()
app.include_router(preferences_routes.router)
app.include_router(auth_routes.router)
app.include_router(jobs_routes.router)
app.include_router(matches_routes.router)
app.include_router(resumes_routes.router)

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
