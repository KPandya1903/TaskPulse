"""Application configuration using Pydantic Settings."""

import os

from pydantic_settings import BaseSettings

# Default to SQLite for development/testing, PostgreSQL for production
_default_db_url = (
    "sqlite+aiosqlite:///./pulse.db"
    if os.environ.get("TESTING")
    else "postgresql+asyncpg://postgres:postgres@localhost:5432/pulse"
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Pulse"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = _default_db_url

    # JWT Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password Settings
    PASSWORD_MIN_LENGTH: int = 8

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    TASK_QUEUE_NAME: str = "pulse:tasks:queue"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
