from functools import lru_cache
from typing import Annotated, Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEFAULT_SECRET_KEY = "local-development-secret-key-change-me"
SECURE_ENVIRONMENTS = {"staging", "prod", "production"}
AI_PROVIDERS = {"internal", "ollama", "groq"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    app_name: str = "gym-routines-api"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://gym_app:gym_app@localhost:5432/gym_app"
    secret_key: str = DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    auth_login_rate_limit_attempts: int = 5
    auth_login_rate_limit_window_seconds: int = 60
    auth_register_rate_limit_attempts: int = 5
    auth_register_rate_limit_window_seconds: int = 600
    ai_provider: str = "internal"
    ai_ollama_base_url: str = "http://localhost:11434"
    ai_ollama_model: str = "llama3.2"
    ai_groq_api_key: str | None = None
    ai_groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_groq_model: str = "llama-3.3-70b-versatile"
    ai_timeout_seconds: int = 20
    ai_external_data_enabled: bool = False
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:19006",
        "http://127.0.0.1:19006",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> Self:
        if self.environment.strip().lower() in SECURE_ENVIRONMENTS and self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError("APP_SECRET_KEY must be changed outside local development.")
        if self.ai_provider not in AI_PROVIDERS:
            raise ValueError("APP_AI_PROVIDER must be internal, ollama or groq.")
        if self.ai_provider == "groq" and not (self.ai_groq_api_key or "").strip():
            raise ValueError("APP_AI_GROQ_API_KEY is required when APP_AI_PROVIDER=groq.")
        if (
            self.environment.strip().lower() in SECURE_ENVIRONMENTS
            and self.ai_provider != "internal"
            and not self.ai_external_data_enabled
        ):
            raise ValueError("APP_AI_EXTERNAL_DATA_ENABLED must be true to use a non-internal AI provider in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
