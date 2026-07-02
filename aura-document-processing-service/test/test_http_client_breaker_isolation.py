"""
Tests for per-host circuit breaker isolation in HttpClient: a failing upstream
must trip only its own breaker, never cascade into a healthy upstream.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.http_client.http_client_settings import HttpClientSettings
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
)

FAILING_URL = "http://failing-upstream.local/x"
HEALTHY_URL = "http://healthy-upstream.local/y"


def _settings() -> HttpClientSettings:
    return HttpClientSettings(
        circuit_breaker_failure_threshold=2,
        retry_max_attempts=0,
        retry_enabled_http_methods="",
    )


async def _client() -> HttpClient:
    client = HttpClient(http_client_settings=_settings())
    await client.start()
    return client


class TestBreakerIsolation:
    async def test_failing_host_trips_only_its_own_breaker(self):
        client = await _client()
        try:
            def _fake_request(method, url, **kwargs):
                if "failing-upstream" in url:
                    raise httpx.ConnectError("boom")
                return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

            with patch.object(client._client, "request", side_effect=_fake_request):
                # Drive the failing host until its breaker opens.
                tripped = False
                for _ in range(5):
                    try:
                        await client.get(FAILING_URL)
                    except HttpClientCircuitBreakerException:
                        tripped = True
                        break
                    except HttpClientConnectionException:
                        continue
                assert tripped, "the failing host's breaker should have opened"

                # The healthy host shares the same HttpClient but a different
                # breaker, so it must remain fully usable.
                response = await client.get(HEALTHY_URL)
                assert response.status_code == 200
        finally:
            await client.stop()

    async def test_breakers_are_created_per_host(self):
        client = await _client()
        try:
            def _fake_request(method, url, **kwargs):
                return httpx.Response(200, request=httpx.Request(method, url))

            with patch.object(client._client, "request", side_effect=_fake_request):
                await client.get(FAILING_URL)
                await client.get(HEALTHY_URL)

            assert set(client._breakers.keys()) == {
                "failing-upstream.local",
                "healthy-upstream.local",
            }
        finally:
            await client.stop()

    async def test_health_check_reports_breakers_by_host(self):
        client = await _client()
        try:
            health = await client.health_check()
            assert health["status"] == "healthy"
            assert "by_host" in health["circuit_breakers"]
        finally:
            await client.stop()
