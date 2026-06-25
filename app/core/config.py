from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Publicly-known placeholder secret shipped in .env.example. The app must refuse
# to boot with this (or any short) secret outside development (CR-01).
_INSECURE_DEFAULT_JWT_SECRET = "changeme-jwt-secret-key-minimum-32-bytes-long"


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

    @model_validator(mode="after")
    def _require_secret_outside_dev(self) -> "Settings":
        """Fail closed if the JWT secret is weak/default outside development (CR-01).

        In development the safe-looking placeholder default is allowed so the
        existing test suite (which runs with environment="development") still
        works. In any other environment the app refuses to boot unless
        JWT_SECRET_KEY is overridden with a 32+ byte random secret — otherwise
        tokens would be signed with a publicly-known secret and anyone could
        forge them for any user.
        """
        if self.environment != "development" and (
            self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET
            or len(self.jwt_secret_key) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be overridden with a 32+ byte random secret "
                "in non-development environments"
            )
        return self


settings = Settings()
