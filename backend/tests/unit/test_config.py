"""Phase 0 — Config tests."""

import pytest
from unittest.mock import patch


class TestConfig:
    """Test application configuration loading."""

    def test_required_env_vars_load_correctly(self):
        """Settings should load with valid environment variables."""
        from app.config import Settings

        settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret",
            MONGODB_URI="mongodb://localhost:27017",
            REDIS_URL="redis://localhost:6379",
        )
        assert settings.SECRET_KEY == "test-secret"
        assert settings.ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
        assert settings.MONGODB_DB == "eros_ai"  # now loaded from .env

    def test_missing_env_var_uses_defaults(self):
        """Settings should use default values when env vars are not set."""
        from app.config import Settings

        settings = Settings(SECRET_KEY="test")
        assert "mongodb" in settings.MONGODB_URI  # Atlas or localhost
        assert settings.REDIS_URL == "redis://localhost:6379"
        assert settings.DIARY_CRON_HOUR == 23
        assert settings.DIARY_CRON_MINUTE == 59
