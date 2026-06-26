"""Unit tests for EnvironmentVariables: the log-level and CORS validators, the
production/development flags, and the numeric field bounds. Settings are built
with _env_file=None so the repo .env never leaks into assertions."""
import pytest
from pydantic import ValidationError

from app.configuration.environment_variables import EnvironmentVariables


def _settings(**overrides) -> EnvironmentVariables:
    base = {"cors_origins": ["http://localhost:3000"]}
    base.update(overrides)
    return EnvironmentVariables(_env_file=None, **base)


class TestLogLevel:
    def test_log_level_is_uppercased(self):
        assert _settings(log_level="info").log_level == "INFO"

    @pytest.mark.parametrize("level", ["debug", "info", "warning", "error", "critical"])
    def test_all_valid_levels_accepted(self, level):
        assert _settings(log_level=level).log_level == level.upper()

    def test_invalid_log_level_raises(self):
        with pytest.raises(ValidationError):
            _settings(log_level="verbose")


class TestCorsOrigins:
    def test_empty_cors_origins_raises(self):
        with pytest.raises(ValidationError):
            _settings(cors_origins=[])

    def test_non_empty_origins_are_kept(self):
        assert _settings(cors_origins=["http://a", "http://b"]).cors_origins == ["http://a", "http://b"]


class TestEnvironmentFlags:
    @pytest.mark.parametrize("value", ["production", "prod", "PRODUCTION", "  Prod  "])
    def test_is_production_true(self, value):
        s = _settings(environment=value)
        assert s.is_production() is True
        assert s.is_development() is False

    @pytest.mark.parametrize("value", ["development", "docker", "staging", ""])
    def test_is_development_true(self, value):
        s = _settings(environment=value)
        assert s.is_production() is False
        assert s.is_development() is True


class TestNumericBounds:
    def test_max_request_body_below_min_raises(self):
        with pytest.raises(ValidationError):
            _settings(max_request_body_bytes=100)

    def test_app_port_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            _settings(app_port=70_000)

    def test_rate_limit_below_min_raises(self):
        with pytest.raises(ValidationError):
            _settings(rate_limit_default_per_window=0)

    def test_defaults(self):
        s = _settings()
        assert s.app_port == 8000
        assert s.app_reload is False
        assert s.log_level == "INFO"
        assert s.max_request_body_bytes == 10 * 1024 * 1024
        assert s.rate_limit_window_seconds == 60
        assert s.rate_limit_default_per_window == 60
        assert s.rate_limit_strict_per_window == 20
