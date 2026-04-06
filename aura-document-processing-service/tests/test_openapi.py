"""Smoke tests for public OpenAPI and docs (no infra)."""


def test_openapi_json_lists_create_document_and_document_query(client) -> None:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    data = response.json()
    paths = data.get("paths", {})
    assert "/api/create-document" in paths
    assert "/api/document-query/documents" in paths
    assert "/api/document-query/document_controllers/{document_id}" in paths


def test_swagger_docs_reachable(client) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
