"""Tests for Phase 0 health endpoint and configuration loading."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings


def test_health_endpoint_returns_200(client: TestClient) -> None:
    """GET /health returns 200 OK with status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings loads expected default values when SECRET_KEY is provided."""
    monkeypatch.setenv("SECRET_KEY", "valid-test-secret")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    monkeypatch.delenv("JOBICY_ENABLED", raising=False)
    monkeypatch.delenv("REMOTEOK_ENABLED", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ENV == "development"
    assert settings.SECRET_KEY == "valid-test-secret"
    assert settings.DATABASE_URL == "sqlite:///./data/app.db"
    assert settings.GROQ_API_KEY == ""
    assert settings.GROQ_MODEL == ""
    assert settings.MAX_UPLOAD_MB == 5
    assert settings.JOBICY_ENABLED is True
    assert settings.REMOTEOK_ENABLED is True


def test_missing_or_empty_secret_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings fails fast when SECRET_KEY is missing or blank."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    monkeypatch.setenv("SECRET_KEY", "   ")
    with pytest.raises(ValidationError, match="SECRET_KEY must not be empty"):
        Settings(_env_file=None)


def test_production_secret_key_must_be_at_least_32_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In production mode, SECRET_KEY shorter than 32 characters raises ValidationError."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "too-short-for-prod")
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(_env_file=None)

    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    settings = Settings(_env_file=None)
    assert len(settings.SECRET_KEY) == 32
