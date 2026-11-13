import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config_core import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(sub: str) -> str:
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": sub, "exp": expire, "iat": time.time()}, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])


# Password reset links: stateless and single-use. The signature covers the user's current password
# hash, so changing the password (by this link or any other way) kills every outstanding link.
RESET_TTL_S = 30 * 60


def _reset_sig(user_id: str, exp: int, password_hash: str) -> str:
    msg = (
        f"pwreset|{user_id}|{exp}|{password_hash}".encode()
    )  # "pwreset|": can't pass for any other signed value
    return hmac.new(get_settings().JWT_SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def make_reset_token(user_id: str, password_hash: str, now: float | None = None) -> str:
    exp = int((time.time() if now is None else now) + RESET_TTL_S)
    return f"{user_id}.{exp}.{_reset_sig(user_id, exp, password_hash)}"


def reset_token_user(token: str) -> str | None:
    parts = token.split(".")
    return parts[0] if len(parts) == 3 and parts[1].isdigit() else None


def reset_token_valid(token: str, password_hash: str, now: float | None = None) -> bool:
    if reset_token_user(token) is None:
        return False
    user_id, exp, sig = token.split(".")
    if int(exp) < (time.time() if now is None else now):
        return False
    return hmac.compare_digest(sig, _reset_sig(user_id, int(exp), password_hash))  # constant-time compare


# Email confirmation links: same token shape as resets, different purpose prefix ("verify|"), so a reset
# token can never confirm an email or vice versa. Signed over the address, so it only confirms that address.
VERIFY_TTL_S = 7 * 24 * 3600


def _verify_sig(user_id: str, exp: int, email: str) -> str:
    msg = f"verify|{user_id}|{exp}|{email.lower()}".encode()
    return hmac.new(get_settings().JWT_SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def make_verify_token(user_id: str, email: str, now: float | None = None) -> str:
    exp = int((time.time() if now is None else now) + VERIFY_TTL_S)
    return f"{user_id}.{exp}.{_verify_sig(user_id, exp, email)}"


def verify_token_valid(token: str, email: str, now: float | None = None) -> bool:
    if reset_token_user(token) is None:
        return False
    user_id, exp, sig = token.split(".")
    if int(exp) < (time.time() if now is None else now):
        return False
    return hmac.compare_digest(sig, _verify_sig(user_id, int(exp), email))


# Unsubscribe links: no expiry (an old email's link must keep working), only power is the weekly email.
def _unsub_sig(user_id: str) -> str:
    msg = f"unsubscribe|{user_id}".encode()  # "unsubscribe|": can't pass for another token
    return hmac.new(get_settings().JWT_SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def make_unsubscribe_token(user_id: str) -> str:
    return f"{user_id}.{_unsub_sig(user_id)}"


def unsubscribe_token_user(token: str) -> str | None:
    user_id, _, sig = (token or "").partition(".")
    return user_id if user_id and sig and hmac.compare_digest(sig, _unsub_sig(user_id)) else None
