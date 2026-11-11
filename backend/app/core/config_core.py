from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    COOKIE_NAME: str = "jobbot_session"
    COOKIE_SECURE: bool = True      # HTTPS only. Local http dev: COOKIE_SECURE=false in .env
    TRUST_CF_CONNECTING_IP: bool = False   # True ONLY when traffic can arrive solely via Cloudflare (Tunnel)
    DOCS_ENABLED: bool = False      # no public /docs, /redoc, /openapi.json. Local dev: DOCS_ENABLED=true in .env

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""        # set in .env, never in code
    EMAIL_FROM: str = ""
    APP_URL: str = "https://jobmatch.bbenard.dev"   # links in emails; never built from the Host header

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_long_enough(cls, v: str) -> str:
        # HS256 with a short secret can be brute-forced offline from any one token: refuse to start.
        if len(v.encode()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 bytes (generate one: openssl rand -hex 32)")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
