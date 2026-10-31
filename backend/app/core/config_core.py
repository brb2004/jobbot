from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    LLM_API_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5:7b-instruct"          # resume sorting: long input, simple task
    JUDGE_MODEL: str = "qwen2.5:14b-instruct"       # judging: short input, harder task
    EMBED_MODEL: str = "nomic-embed-text"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""        # set in .env, never in code
    EMAIL_FROM: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
