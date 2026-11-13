import math

from fastapi import HTTPException

from app.core.ratelimit_core import RateLimiter

QUARTER_HOUR, HOUR = 900, 3600

LOGIN_FAILS = RateLimiter(5, QUARTER_HOUR)
LOGIN_IP = RateLimiter(30, QUARTER_HOUR)
LOGIN_EMAIL = RateLimiter(10**9, QUARTER_HOUR)
TARPIT_S = 2.0

REGISTER_IP = RateLimiter(5, HOUR)
SIGNUP_EMAIL = RateLimiter(3, HOUR)
FORGOT_IP = RateLimiter(10, HOUR)
FORGOT_EMAIL = RateLimiter(3, HOUR)
VERIFY_RESEND = RateLimiter(3, HOUR)
FEEDBACK_USER = RateLimiter(5, HOUR)
FEEDBACK_IP = RateLimiter(20, HOUR)

FREE_FAILS = 5
DELAY_S, MAX_DELAY_S = 1.0, 16.0


def account_delay(fails: int) -> float:
    if fails < FREE_FAILS:
        return 0.0
    return min(MAX_DELAY_S, DELAY_S * 2 ** (fails - FREE_FAILS))


def too_many(wait: float, message: str) -> HTTPException:
    return HTTPException(429, message, headers={"Retry-After": str(math.ceil(wait))})


def reset_all() -> None:
    for value in globals().values():
        if isinstance(value, RateLimiter):
            value.reset()
