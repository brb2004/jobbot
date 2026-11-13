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
    COOKIE_SECURE: bool = True
    TRUST_CF_CONNECTING_IP: bool = False
    DOCS_ENABLED: bool = False

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    EMAIL_REPLY_TO: str = ""
    APP_URL: str = "https://skillfit.dev"
    NOTIFY_URL: str = ""

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_long_enough(cls, v: str) -> str:
        if len(v.encode()) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 bytes (generate one: openssl rand -hex 32)")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
