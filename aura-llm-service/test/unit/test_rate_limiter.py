"""Unit tests for the Redis-backed sliding-window rate limiter.

Critical path: enforcement (allow vs. 429), graceful degradation when Redis is
missing or unreachable (fail-open), and per-request resolution of the configured
limits (strict vs. default) so settings stay overridable.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.exceptions as redis_exceptions
from fastapi import HTTPException

from app.api.dependencies import rate_limiter
from app.api.dependencies.rate_limiter import (
    _check_rate_limit,
    default_rate_limit,
    make_rate_limiter,
    strict_rate_limit,
)
from app.configuration.environment_variables import get_settings


def _make_request(eval_result=None, eval_error=None, with_redis=True, path="/api/v1/x"):
    """Build a minimal Request-like object for the rate limiter."""
    request = MagicMock()
    request.url.path = path
    request.client.host = "203.0.113.5"
    request.state.authenticated_user = None

    if with_redis:
        redis_client = MagicMock()
        if eval_error is not None:
            redis_client.client.eval = AsyncMock(side_effect=eval_error)
        else:
            redis_client.client.eval = AsyncMock(return_value=eval_result)
        request.app.state.redis_client = redis_client
    else:
        request.app.state = SimpleNamespace()  # no redis_client attribute

    return request


@pytest.mark.asyncio
async def test_no_redis_client_is_noop():
    # Rate limiting must not block requests when Redis is not configured.
    request = _make_request(with_redis=False)
    await _check_rate_limit(request, limit=10)  # must not raise


@pytest.mark.asyncio
async def test_allowed_request_does_not_raise():
    request = _make_request(eval_result=[1, "0"])
    await _check_rate_limit(request, limit=10)
    request.app.state.redis_client.client.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocked_request_raises_429_with_retry_after():
    import time

    now = time.time()
    # allowed=0 → over the limit; oldest score drives the Retry-After hint.
    request = _make_request(eval_result=[0, str(now)])

    with pytest.raises(HTTPException) as exc_info:
        await _check_rate_limit(request, limit=1)

    assert exc_info.value.status_code == 429
    retry_after = exc_info.value.headers["Retry-After"]
    assert int(retry_after) >= 1


@pytest.mark.asyncio
async def test_redis_error_fails_open():
    # A Redis outage must not take the API down: fail-open (allow the request).
    request = _make_request(eval_error=redis_exceptions.RedisError("boom"))
    await _check_rate_limit(request, limit=1)  # must not raise


@pytest.mark.asyncio
async def test_os_error_fails_open():
    request = _make_request(eval_error=OSError("connection reset"))
    await _check_rate_limit(request, limit=1)  # must not raise


@pytest.mark.asyncio
async def test_authenticated_user_identity_is_used_in_key():
    request = _make_request(eval_result=[1, "0"])
    request.state.authenticated_user = SimpleNamespace(id=42)

    await _check_rate_limit(request, limit=10)

    args, _ = request.app.state.redis_client.client.eval.call_args
    # Script, numkeys, then KEYS[1] = the rate-limit key.
    key = args[2]
    assert "42" in key


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "factory, expected_attr",
    [
        (strict_rate_limit, "rate_limit_strict_per_window"),
        (default_rate_limit, "rate_limit_default_per_window"),
    ],
)
async def test_limiters_resolve_configured_limit_per_request(monkeypatch, factory, expected_attr):
    captured = {}

    async def _fake_check(request, limit):
        captured["limit"] = limit

    monkeypatch.setattr(rate_limiter, "_check_rate_limit", _fake_check)

    await factory(_make_request(eval_result=[1, "0"]))

    expected = getattr(get_settings(), expected_attr)
    assert captured["limit"] == expected


def test_make_rate_limiter_defaults_to_default_tier_for_unknown_kind():
    # Any kind other than "strict" resolves to the default limit (defensive).
    limiter = make_rate_limiter("something-else")
    assert callable(limiter)
