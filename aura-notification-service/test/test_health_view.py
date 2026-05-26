"""
Tests for the health check endpoint:
  GET /api/v1/health
"""
import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError

URL = "/api/v1/health"

_DB = "apps.notification.api.views.health_view.connection"
_REDIS = "apps.notification.api.views.health_view.redis_lib"
_KOMBU_CONN = "kombu.Connection"


def _redis_ok():
    """Returns a mock Redis client that responds to ping and close."""
    mock_redis = MagicMock()
    client = MagicMock()
    client.ping.return_value = True
    mock_redis.Redis.from_url.return_value = client
    return mock_redis


def _kombu_ok():
    """Returns a mock Kombu connection that connects successfully."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.ensure_connection.return_value = None
    return conn


class TestHealthCheckView:
    def test_no_authentication_required(self, api_client):
        with (
            patch(_DB),
            patch(_REDIS, _redis_ok()),
            patch(_KOMBU_CONN, return_value=_kombu_ok()),
        ):
            response = api_client.get(URL)

        assert response.status_code in (200, 503)

    def test_all_healthy_returns_200_with_ok_status(self, api_client):
        with (
            patch(_DB),
            patch(_REDIS, _redis_ok()),
            patch(_KOMBU_CONN, return_value=_kombu_ok()),
        ):
            response = api_client.get(URL)

        assert response.status_code == 200
        assert response.data["status"] == "ok"
        assert response.data["checks"]["database"] == "ok"
        assert response.data["checks"]["redis"] == "ok"
        assert response.data["checks"]["broker"] == "ok"

    def test_database_down_returns_503_and_degraded(self, api_client):
        with (
            patch(_DB) as mock_db,
            patch(_REDIS, _redis_ok()),
            patch(_KOMBU_CONN, return_value=_kombu_ok()),
        ):
            mock_db.ensure_connection.side_effect = OperationalError("DB unavailable")
            response = api_client.get(URL)

        assert response.status_code == 503
        assert response.data["status"] == "degraded"
        assert response.data["checks"]["database"] == "error"
        assert response.data["checks"]["redis"] == "ok"

    def test_redis_down_returns_503_and_degraded(self, api_client):
        mock_redis = MagicMock()
        client = MagicMock()
        client.ping.side_effect = Exception("Redis connection refused")
        mock_redis.Redis.from_url.return_value = client

        with (
            patch(_DB),
            patch(_REDIS, mock_redis),
            patch(_KOMBU_CONN, return_value=_kombu_ok()),
        ):
            response = api_client.get(URL)

        assert response.status_code == 503
        assert response.data["status"] == "degraded"
        assert response.data["checks"]["redis"] == "error"
        assert response.data["checks"]["database"] == "ok"

    def test_broker_down_returns_503_and_degraded(self, api_client):
        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(side_effect=Exception("Broker unreachable"))
        failing_conn.__exit__ = MagicMock(return_value=False)

        with (
            patch(_DB),
            patch(_REDIS, _redis_ok()),
            patch(_KOMBU_CONN, return_value=failing_conn),
        ):
            response = api_client.get(URL)

        assert response.status_code == 503
        assert response.data["status"] == "degraded"
        assert response.data["checks"]["broker"] == "error"
        assert response.data["checks"]["database"] == "ok"

    def test_multiple_failures_all_reported_as_error(self, api_client):
        mock_redis = MagicMock()
        mock_redis.Redis.from_url.return_value.ping.side_effect = Exception("Redis down")

        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(side_effect=Exception("Broker down"))
        failing_conn.__exit__ = MagicMock(return_value=False)

        with (
            patch(_DB) as mock_db,
            patch(_REDIS, mock_redis),
            patch(_KOMBU_CONN, return_value=failing_conn),
        ):
            mock_db.ensure_connection.side_effect = OperationalError("DB down")
            response = api_client.get(URL)

        assert response.status_code == 503
        assert response.data["checks"]["database"] == "error"
        assert response.data["checks"]["redis"] == "error"
        assert response.data["checks"]["broker"] == "error"

    def test_response_always_includes_all_three_check_keys(self, api_client):
        with (
            patch(_DB),
            patch(_REDIS, _redis_ok()),
            patch(_KOMBU_CONN, return_value=_kombu_ok()),
        ):
            response = api_client.get(URL)

        checks = response.data["checks"]
        assert set(checks.keys()) == {"database", "redis", "broker"}
