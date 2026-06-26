"""Unit tests for the shared HttpClient: exception mapping, the not-started
guard, and the per-host circuit breaker (trips after the configured number of
failures; upstream 4xx responses do not trip it)."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientNotStartedException,
    HttpClientServerException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.http_client.http_client_settings import HttpClientSettings


def _settings(**overrides) -> HttpClientSettings:
    base = dict(circuit_breaker_failure_threshold=2, retry_max_attempts=0)
    base.update(overrides)
    return HttpClientSettings(**base)


async def _started_client(**overrides) -> HttpClient:
    client = HttpClient(http_client_settings=_settings(**overrides))
    await client.start()
    return client


def _install_fake_transport(client: HttpClient, *, request_mock: AsyncMock) -> None:
    """Replace the underlying httpx client with a mock whose ``request`` is
    controlled by the test and whose ``aclose`` is awaitable (so ``stop()`` is clean)."""
    fake = MagicMock()
    fake.request = request_mock
    fake.aclose = AsyncMock()
    client._client = fake


def _status_error_response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=httpx.Request("POST", "http://up.test/x"), response=MagicMock(status_code=status_code)
    )
    return response


@pytest.mark.asyncio
async def test_request_before_start_raises_not_started():
    client = HttpClient(http_client_settings=_settings())
    with pytest.raises(HttpClientNotStartedException):
        await client.post("http://up.test/x", json={})


@pytest.mark.asyncio
async def test_timeout_is_mapped():
    client = await _started_client()
    try:
        _install_fake_transport(client, request_mock=AsyncMock(side_effect=httpx.TimeoutException("slow")))
        with pytest.raises(HttpClientTimeoutException):
            await client.post("http://up.test/x", json={})
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_connection_error_is_mapped():
    client = await _started_client()
    try:
        _install_fake_transport(client, request_mock=AsyncMock(side_effect=httpx.ConnectError("refused")))
        with pytest.raises(HttpClientConnectionException):
            await client.post("http://up.test/x", json={})
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_upstream_status_error_is_mapped_with_status_code():
    client = await _started_client()
    try:
        _install_fake_transport(client, request_mock=AsyncMock(return_value=_status_error_response(503)))
        with pytest.raises(HttpClientException) as exc_info:
            await client.post("http://up.test/x", json={})
        assert exc_info.value.status_code == 503
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_retryable_5xx_is_retried_for_idempotent_method():
    client = await _started_client(
        retry_max_attempts=3,
        retry_backoff_min_seconds=0.01,
        retry_backoff_max_seconds=0.02,
    )
    try:
        request_mock = AsyncMock(return_value=_status_error_response(503))
        _install_fake_transport(client, request_mock=request_mock)
        with pytest.raises(HttpClientServerException) as exc_info:
            await client.get("http://up.test/x")
        assert exc_info.value.status_code == 503
        assert request_mock.call_count == 3
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_non_retryable_5xx_is_not_retried():
    client = await _started_client(
        retry_max_attempts=3,
        retry_backoff_min_seconds=0.01,
        retry_backoff_max_seconds=0.02,
    )
    try:
        request_mock = AsyncMock(return_value=_status_error_response(500))
        _install_fake_transport(client, request_mock=request_mock)
        with pytest.raises(HttpClientException) as exc_info:
            await client.get("http://up.test/x")
        assert exc_info.value.status_code == 500
        assert not isinstance(exc_info.value, HttpClientServerException)
        assert request_mock.call_count == 1
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_retryable_5xx_not_retried_for_non_idempotent_method():
    client = await _started_client(
        retry_max_attempts=3,
        retry_backoff_min_seconds=0.01,
        retry_backoff_max_seconds=0.02,
    )
    try:
        request_mock = AsyncMock(return_value=_status_error_response(503))
        _install_fake_transport(client, request_mock=request_mock)
        with pytest.raises(HttpClientServerException):
            await client.post("http://up.test/x", json={})
        assert request_mock.call_count == 1
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold_failures():
    threshold = 3
    client = await _started_client(circuit_breaker_failure_threshold=threshold)
    try:
        _install_fake_transport(client, request_mock=AsyncMock(side_effect=httpx.ConnectError("refused")))

        for _ in range(threshold - 1):
            with pytest.raises(HttpClientConnectionException):
                await client.post("http://up.test/x", json={})

        with pytest.raises(HttpClientCircuitBreakerException):
            await client.post("http://up.test/x", json={})

        with pytest.raises(HttpClientCircuitBreakerException):
            await client.post("http://up.test/x", json={})
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_upstream_4xx_does_not_trip_the_breaker():
    client = await _started_client(circuit_breaker_failure_threshold=2)
    try:
        _install_fake_transport(client, request_mock=AsyncMock(return_value=_status_error_response(404)))

        for _ in range(5):
            with pytest.raises(HttpClientException) as exc_info:
                await client.post("http://up.test/x", json={})
            assert exc_info.value.status_code == 404
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_per_host_breaker_isolation():
    threshold = 2
    client = await _started_client(circuit_breaker_failure_threshold=threshold)
    try:
        _install_fake_transport(client, request_mock=AsyncMock(side_effect=httpx.ConnectError("refused")))

        with pytest.raises(HttpClientConnectionException):
            await client.post("http://host-a.test/x", json={})
        with pytest.raises(HttpClientCircuitBreakerException):
            await client.post("http://host-a.test/x", json={})

        with pytest.raises(HttpClientConnectionException):
            await client.post("http://host-b.test/y", json={})
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_health_check_reports_not_started():
    client = HttpClient(http_client_settings=_settings())
    result = await client.health_check()
    assert result["status"] == "unhealthy"
    assert result["started"] is False
