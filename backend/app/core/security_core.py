from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config_core import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(sub: str) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": expire}, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])