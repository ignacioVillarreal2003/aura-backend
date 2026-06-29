def test_health_returns_ok(anon_client):
    response = anon_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.data["status"] == "ok"


def test_health_accessible_without_auth(anon_client):
    response = anon_client.get("/api/v1/health")
    assert response.status_code == 200
