from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses extra="ignore" so that variables defined in .env.example for future
    phases (MySQL, JWT, Anthropic, Ollama) do not raise validation errors during
    Phase 1 when those services are not yet configured.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()
