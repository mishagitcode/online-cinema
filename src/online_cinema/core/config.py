from functools import lru_cache

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    activation_token_ttl_hours: int = 24
    password_reset_token_ttl_hours: int = 2
    database_url: str = "sqlite+aiosqlite:///./online_cinema.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: EmailStr = Field(default="no-reply@example.com")
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "avatars"
    docs_username: str = "admin"
    docs_password: str = "admin"
    bootstrap_admin_email: EmailStr = Field(default="admin@example.com")
    bootstrap_admin_password: str = "Admin123!"
    payment_provider: str = "fake"
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

