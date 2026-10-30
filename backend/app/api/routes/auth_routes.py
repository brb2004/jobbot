from fastapi import APIRouter, Depends, HTTPException
from app.api.deps_api import get_current_user
from app.core.db_core import get_session
from app.core.security_core import create_access_token
from app.schemas.auth_schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth_services as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, s=Depends(get_session)):
    try:
        user = await auth_service.register(s, body.email, body.password)
    except auth_service.EmailTaken:
        raise HTTPException(409, "Email already registered")
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, s=Depends(get_session)):
    user = await auth_service.authenticate(s, body.email, body.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")    # one message for both cases
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def me(s=Depends(get_session), user_id=Depends(get_current_user)):
    user = await auth_service.get(s, user_id)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user