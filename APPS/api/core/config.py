from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    APP_NAME: str = "CAT AI API"
    DEBUG: bool = True

    # Security
    JWT_SECRET: str = "change-me-in-production-use-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/catai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3
    S3_BUCKET_FILES: str = "cat-ai-files"
    S3_BUCKET_ASSETS: str = "cat-ai-assets"
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # AI Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_MODEL: str = "gpt-4o"
    DEFAULT_PROVIDER: str = "openai"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Rate limits (requests per minute)
    RATE_LIMIT_FREE: int = 20
    RATE_LIMIT_PRO: int = 100
    RATE_LIMIT_TEAM: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()