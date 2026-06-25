from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses extra="ignore" so that variables defined in .env.example for future
    phases (JWT, Anthropic, Ollama) do not raise validation errors when those
    services are not yet configured.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Database — MySQL via asyncmy + SQLAlchemy 2
    # Shape: mysql+asyncmy://user:pass@host:port/db?charset=utf8mb4
    # In Docker Compose the host is the service name ("mysql"), not localhost.
    database_url: str = "mysql+asyncmy://secondbrain:changeme-password@mysql:3306/secondbrain?charset=utf8mb4"

    # JWT (Phase 3) — read from .env; defaults are safe-looking-but-insecure placeholders.
    # In production, override JWT_SECRET_KEY with a 32+ byte random secret.
    jwt_secret_key: str = "changeme-jwt-secret-key-minimum-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


settings = Settings()
