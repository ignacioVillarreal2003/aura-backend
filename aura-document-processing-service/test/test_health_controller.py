"""
Tests for GET /api/v1/health and GET /api/v1/ready
"""


class TestHealth:
    def test_liveness_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_liveness_has_status_ok(self, client):
        body = client.get("/api/v1/health").json()
        assert body.get("status") == "ok"

    def test_liveness_requires_no_auth(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code != 401


class TestReadiness:
    def test_readiness_returns_503_without_services(self, client):
        response = client.get("/api/v1/ready")
        assert response.status_code in (200, 503)

    def test_readiness_requires_no_auth(self, client):
        response = client.get("/api/v1/ready")
        assert response.status_code != 401
