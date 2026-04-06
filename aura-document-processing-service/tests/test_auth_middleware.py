"""Authentication middleware behaviour on create-document (no service registered)."""

from tests.conftest import attach_auth_and_db, service_auth_headers


def test_create_document_without_credentials_returns_401(client, app) -> None:
    attach_auth_and_db(app)
    response = client.post("/api/create-document")
    assert response.status_code == 401
    body = response.json()
    assert body.get("error") == "missing_token"


def test_create_document_invalid_service_api_key_returns_403(client, app) -> None:
    attach_auth_and_db(app)
    headers = service_auth_headers(api_key="definitely-not-the-configured-key")
    response = client.post("/api/create-document", headers=headers)
    assert response.status_code == 403
    body = response.json()
    assert body.get("error") == "invalid_service_key"


def test_create_document_valid_service_auth_reaches_dependency_layer_503(client, app) -> None:
    attach_auth_and_db(app)
    response = client.post("/api/create-document", headers=service_auth_headers())
    assert response.status_code == 503
    payload = response.json()
    assert "CreateDocumentService" in (payload.get("message") or payload.get("detail") or "")
