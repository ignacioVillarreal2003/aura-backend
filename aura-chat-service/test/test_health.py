from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db(mocker):
    return mocker.patch("aura_chat_service.urls.connection.ensure_connection")


@pytest.fixture
def mock_redis(mocker):
    mock_r = MagicMock()
    mocker.patch("aura_chat_service.urls.redis_lib.Redis.from_url", return_value=mock_r)
    return mock_r


def test_health_ok(anon_client, mock_db, mock_redis):
    mock_redis.ping.return_value = True
    response = anon_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["checks"]["database"] == "ok"
    assert response.data["checks"]["redis"] == "ok"


def test_health_db_down(anon_client, mock_db, mock_redis, mocker):
    from django.db import OperationalError
    mock_db.side_effect = OperationalError("connection refused")
    mock_redis.ping.return_value = True

    response = anon_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.data["status"] == "degraded"
    assert response.data["checks"]["database"] == "error"
    assert response.data["checks"]["redis"] == "ok"


def test_health_redis_down(anon_client, mock_db, mock_redis):
    mock_redis.ping.side_effect = Exception("connection refused")

    response = anon_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.data["status"] == "degraded"
    assert response.data["checks"]["database"] == "ok"
    assert response.data["checks"]["redis"] == "error"


def test_health_both_down(anon_client, mock_db, mock_redis):
    from django.db import OperationalError
    mock_db.side_effect = OperationalError("db down")
    mock_redis.ping.side_effect = Exception("redis down")

    response = anon_client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.data["status"] == "degraded"
    assert response.data["checks"]["database"] == "error"
    assert response.data["checks"]["redis"] == "error"


def test_health_no_auth_required(anon_client, mock_db, mock_redis):
    """Health endpoint must be accessible without credentials."""
    mock_redis.ping.return_value = True
    response = anon_client.get("/api/v1/health")
    assert response.status_code == 200
