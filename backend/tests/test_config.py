import pytest

from app.core.config import Settings


def test_settings_load_database_url_from_app_env_prefix(monkeypatch) -> None:
    database_url = "postgresql+psycopg://user:password@localhost:5432/test_db"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)

    settings = Settings()

    assert settings.database_url == database_url


def test_settings_reject_default_secret_key_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "local-development-secret-key-change-me")

    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Settings()


def test_settings_reject_default_secret_key_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_SECRET_KEY", "local-development-secret-key-change-me")

    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Settings()


def test_settings_reject_unknown_ai_provider(monkeypatch) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="APP_AI_PROVIDER"):
        Settings()


def test_settings_parse_cors_origins_from_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://zenith.vercel.app, https://preview.example.com")

    settings = Settings()

    assert settings.cors_origins == ["https://zenith.vercel.app", "https://preview.example.com"]


def test_settings_require_ai_external_data_flag_for_non_internal_provider_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "production-secret-key")
    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    monkeypatch.setenv("APP_AI_EXTERNAL_DATA_ENABLED", "false")

    with pytest.raises(ValueError, match="APP_AI_EXTERNAL_DATA_ENABLED"):
        Settings()


def test_settings_accept_groq_with_api_key_and_external_data_enabled_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_SECRET_KEY", "production-secret-key")
    monkeypatch.setenv("APP_AI_PROVIDER", "groq")
    monkeypatch.setenv("APP_AI_GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("APP_AI_EXTERNAL_DATA_ENABLED", "true")

    settings = Settings()

    assert settings.ai_provider == "groq"
    assert settings.ai_groq_api_key == "test-groq-key"


def test_settings_require_groq_api_key(monkeypatch) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "groq")

    with pytest.raises(ValueError, match="APP_AI_GROQ_API_KEY"):
        Settings()
