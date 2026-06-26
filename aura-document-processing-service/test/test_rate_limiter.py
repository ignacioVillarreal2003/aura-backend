from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status

from app.api.dependencies import rate_limiter
from app.api.dependencies.rate_limiter import (
    _check_rate_limit,
    make_rate_limiter,
)
from app.api.dependencies.rate_limiter_settings import RateLimiterSettings



def _redis(*, allowed=1, retry_after=0, eval_error=None):
    client = MagicMock()
    if eval_error is not None:
        client.client.eval = AsyncMock(side_effect=eval_error)
    else:
        client.client.eval = AsyncMock(return_value=[allowed, retry_after])
    return client


def _request(*, redis_client=None, user_id=None, path="/api/v1/x", host="1.2.3.4"):
    req = MagicMock()
    req.app.state.redis_client = redis_client
    req.state.authenticated_user = MagicMock(id=user_id) if user_id is not None else None
    req.url.path = path
    req.client.host = host
    return req


@pytest.fixture
def use_settings(monkeypatch):
    """Swap the module-level settings singleton for the duration of a test."""
    def _apply(**kwargs):
        settings = RateLimiterSettings(**kwargs)
        monkeypatch.setattr(rate_limiter, "_settings", settings)
        return settings

    return _apply



class TestRateLimiterSettings:
    def test_defaults_match_previous_hardcoded_values(self):
        settings = RateLimiterSettings()
        assert settings.strict_rate == 20
        assert settings.default_rate == 60
        assert settings.window_seconds == 60
        assert settings.fail_open is True

    def test_env_overrides_are_picked_up(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_STRICT_RATE", "5")
        monkeypatch.setenv("RATE_LIMIT_DEFAULT_RATE", "200")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "30")
        monkeypatch.setenv("RATE_LIMIT_FAIL_OPEN", "false")
        settings = RateLimiterSettings()
        assert settings.strict_rate == 5
        assert settings.default_rate == 200
        assert settings.window_seconds == 30
        assert settings.fail_open is False

    def test_strict_above_default_is_rejected(self):
        with pytest.raises(ValueError):
            RateLimiterSettings(strict_rate=100, default_rate=50)



class TestBackendUnavailablePolicy:
    async def test_missing_redis_fails_open_by_default(self, use_settings):
        use_settings(fail_open=True)
        await _check_rate_limit(_request(redis_client=None), limit=20)

    async def test_missing_redis_fails_closed_when_configured(self, use_settings):
        use_settings(fail_open=False)
        with pytest.raises(HTTPException) as exc:
            await _check_rate_limit(_request(redis_client=None), limit=20)
        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_redis_error_fails_open_when_configured(self, use_settings):
        use_settings(fail_open=True)
        redis = _redis(eval_error=RuntimeError("connection reset"))
        await _check_rate_limit(_request(redis_client=redis, user_id=1), limit=20)

    async def test_redis_error_fails_closed_when_configured(self, use_settings):
        use_settings(fail_open=False)
        redis = _redis(eval_error=RuntimeError("connection reset"))
        with pytest.raises(HTTPException) as exc:
            await _check_rate_limit(_request(redis_client=redis, user_id=1), limit=20)
        assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE



class TestLimitEnforcement:
    async def test_allowed_request_passes(self, use_settings):
        use_settings()
        redis = _redis(allowed=1)
        await _check_rate_limit(_request(redis_client=redis, user_id=7), limit=60)

    async def test_blocked_request_raises_429_with_retry_after(self, use_settings):
        use_settings()
        redis = _redis(allowed=0, retry_after=42)
        with pytest.raises(HTTPException) as exc:
            await _check_rate_limit(_request(redis_client=redis, user_id=7), limit=60)
        assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.value.headers["Retry-After"] == "42"

    async def test_window_seconds_from_settings_is_passed_to_redis(self, use_settings):
        use_settings(window_seconds=30)
        redis = _redis(allowed=1)
        await _check_rate_limit(_request(redis_client=redis, user_id=7), limit=60)
        args = redis.client.eval.await_args.args
        assert args[4] == 30
        assert args[5] == 60

    async def test_identity_falls_back_to_client_host_when_anonymous(self, use_settings):
        use_settings()
        redis = _redis(allowed=1)
        await _check_rate_limit(
            _request(redis_client=redis, user_id=None, host="9.9.9.9", path="/p"), limit=60
        )
        key = redis.client.eval.await_args.args[2]
        assert key == "rl:9.9.9.9:/p"



class TestMakeRateLimiter:
    async def test_returns_dependency_that_enforces_limit(self, use_settings):
        use_settings()
        redis = _redis(allowed=0, retry_after=1)
        limiter = make_rate_limiter(20)
        with pytest.raises(HTTPException):
            await limiter(_request(redis_client=redis, user_id=1))
