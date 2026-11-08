from functools import lru_cache
from typing import Annotated, Any, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_SECRET_KEY = "local-development-secret-key-change-me"
SECURE_ENVIRONMENTS = {"staging", "prod", "production"}
AI_PROVIDERS = {"internal", "ollama", "groq"}
EMAIL_PROVIDERS = {"console", "smtp", "resend"}
COOKIE_SAMESITE = {"strict", "lax", "none"}


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
    auth_login_email_rate_limit_attempts: int = 20
    auth_login_email_rate_limit_window_seconds: int = 900
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
    ai_rate_limit_per_minute: int = Field(default=10, ge=1)
    ai_rate_limit_per_day: int = Field(default=150, ge=1)
    # Emails transaccionales. 0 EUR: smtp con Gmail (contrasena de aplicacion) o Brevo gratis.
    email_provider: str = "console"
    email_from: str = "Zenith <no-reply@localhost>"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    resend_api_key: str | None = None
    # URL publica de la web para enlaces de email (verificar / restablecer contrasena).
    frontend_base_url: str = "http://localhost:8081"
    email_token_rate_limit_attempts: int = Field(default=3, ge=1)
    email_token_rate_limit_window_seconds: int = Field(default=900, ge=1)
    # Refresh token de la web en cookie httpOnly (la web llega a la API por el proxy /api de Vercel).
    refresh_cookie_name: str = "zenith_refresh"
    refresh_cookie_path: str = "/"
    refresh_cookie_secure: bool = True
    refresh_cookie_samesite: str = "strict"
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
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
        if self.email_provider not in EMAIL_PROVIDERS:
            raise ValueError("APP_EMAIL_PROVIDER must be console, smtp or resend.")
        if self.email_provider == "smtp" and not (self.smtp_username and self.smtp_password):
            raise ValueError("APP_SMTP_USERNAME and APP_SMTP_PASSWORD are required when APP_EMAIL_PROVIDER=smtp.")
        if self.email_provider == "resend" and not (self.resend_api_key or "").strip():
            raise ValueError("APP_RESEND_API_KEY is required when APP_EMAIL_PROVIDER=resend.")
        if self.refresh_cookie_samesite not in COOKIE_SAMESITE:
            raise ValueError("APP_REFRESH_COOKIE_SAMESITE must be strict, lax or none.")
        if self.ai_provider not in AI_PROVIDERS:
            raise ValueError("APP_AI_PROVIDER must be internal, ollama or groq.")
        if self.ai_provider == "groq" and not (self.ai_groq_api_key or "").strip():
            raise ValueError("APP_AI_GROQ_API_KEY is required when APP_AI_PROVIDER=groq.")
        if (
            self.environment.strip().lower() in SECURE_ENVIRONMENTS
            and self.ai_provider != "internal"
            and not self.ai_external_data_enabled
        ):
            raise ValueError(
                "APP_AI_EXTERNAL_DATA_ENABLED must be true to use a non-internal AI provider in production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
