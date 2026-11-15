from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRET = "dev-jwt-secret-change-in-production"
INSECURE_RAG_API_KEY = "dev-secret-key-change-in-production"


class Settings(BaseSettings):
    # No localhost fallback: pydantic raises a clear error if DATABASE_URL is missing.
    DATABASE_URL: str
    GEMINI_API_KEY: str = "fake-key"
    RAG_API_KEY: str = INSECURE_RAG_API_KEY
    JWT_SECRET: str = INSECURE_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7  # 7 days
    # Set ENVIRONMENT=production on Render. Dev defaults are rejected there.
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_production(self) -> Self:
        if self.is_production:
            if self.JWT_SECRET == INSECURE_JWT_SECRET:
                raise ValueError("JWT_SECRET must be set to a real secret in production")
            if self.RAG_API_KEY == INSECURE_RAG_API_KEY:
                raise ValueError("RAG_API_KEY must be set to a real key in production")
        return self


settings = Settings()  # type: ignore[call-arg]
