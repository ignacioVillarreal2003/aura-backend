import pytest

pytestmark = pytest.mark.django_db


def test_health_live_returns_200(api_client):
    response = api_client.get("/health/live")
    assert response.status_code == 200


def test_health_ready_returns_200(api_client):
    response = api_client.get("/health/ready")
    assert response.status_code == 200
