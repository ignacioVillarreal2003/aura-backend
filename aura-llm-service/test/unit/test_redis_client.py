"""Unit tests for RedisClient: the uninitialized guard, ping-on-init,
idempotent initialization, resource cleanup on failed init, the health check,
and credential redaction in the logged URL. The redis driver is mocked, so no
real Redis server is required."""
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.infrastructure.persistence.memory_database.redis_client.redis_client as redis_module
from app.infrastructure.persistence.memory_database.redis_client.redis_client import RedisClient
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings


def _settings(url: str = "redis://user:pass@localhost:6379/0") -> RedisClientSettings:
    return RedisClientSettings(url=url)


def _patch_redis(monkeypatch, *, ping_error: Exception | None = None):
    pool = MagicMock()
    pool.aclose = AsyncMock()
    client = MagicMock()
    client.ping = AsyncMock(side_effect=ping_error)
    client.aclose = AsyncMock()
    monkeypatch.setattr(
        redis_module.aioredis.ConnectionPool,
        "from_url",
        MagicMock(return_value=pool),
    )
    monkeypatch.setattr(redis_module.aioredis, "Redis", MagicMock(return_value=client))
    return pool, client


def test_client_property_before_initialize_raises():
    rc = RedisClient(_settings())
    with pytest.raises(RuntimeError):
        _ = rc.client


async def test_initialize_pings_and_exposes_client(monkeypatch):
    pool, client = _patch_redis(monkeypatch)
    rc = RedisClient(_settings())
    await rc.initialize()
    client.ping.assert_awaited_once()
    assert rc.client is client
    await rc.dispose()
    client.aclose.assert_awaited()
    pool.aclose.assert_awaited()


async def test_initialize_is_idempotent(monkeypatch):
    _, client = _patch_redis(monkeypatch)
    rc = RedisClient(_settings())
    await rc.initialize()
    await rc.initialize()
    client.ping.assert_awaited_once()


async def test_initialize_failure_closes_resources_and_reraises(monkeypatch):
    pool, client = _patch_redis(monkeypatch, ping_error=ConnectionError("refused"))
    rc = RedisClient(_settings())
    with pytest.raises(ConnectionError):
        await rc.initialize()
    client.aclose.assert_awaited()
    pool.aclose.assert_awaited()
    with pytest.raises(RuntimeError):
        _ = rc.client


async def test_health_check_false_when_not_initialized():
    rc = RedisClient(_settings())
    assert await rc.health_check() is False


async def test_health_check_true_when_ping_succeeds(monkeypatch):
    _patch_redis(monkeypatch)
    rc = RedisClient(_settings())
    await rc.initialize()
    try:
        assert await rc.health_check() is True
    finally:
        await rc.dispose()


async def test_health_check_false_when_ping_fails(monkeypatch):
    _, client = _patch_redis(monkeypatch)
    rc = RedisClient(_settings())
    await rc.initialize()
    client.ping = AsyncMock(side_effect=ConnectionError("dropped"))
    assert await rc.health_check() is False
    await rc.dispose()


async def test_redacted_url_hides_credentials(monkeypatch):
    _patch_redis(monkeypatch)
    rc = RedisClient(_settings("redis://user:secret@localhost:6379/0"))
    await rc.initialize()
    try:
        redacted = rc._redacted_url()
        assert "secret" not in redacted
        assert "user" not in redacted
        assert "localhost" in redacted
    finally:
        await rc.dispose()
