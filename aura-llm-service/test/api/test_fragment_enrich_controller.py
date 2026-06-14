"""
Tests for POST /api/v1/fragment-enrich
"""
from app.domain.dtos.processing.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse

URL = "/api/v1/fragment-enrich"

VALID_BODY = {
    "content": "La empresa Acme S.A. firmó un contrato el 10 de enero de 2024.",
}

_RESPONSE = EnrichFragmentResponse(
    summary="Fragmento sobre un contrato firmado por Acme S.A.",
    entities={"ORGANIZATION": "Acme S.A.", "DATE": "10 de enero de 2024"},
    topics=["contratos", "empresas"],
)


class TestFragmentEnrichAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_fragment_enrich_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_fragment_enrich_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestFragmentEnrichValidation:
    def test_blank_content_returns_422(self, client, auth_headers, mock_fragment_enrich_service):
        response = client.post(URL, json={"content": "  "}, headers=auth_headers)
        assert response.status_code == 422

    def test_empty_content_returns_422(self, client, auth_headers, mock_fragment_enrich_service):
        response = client.post(URL, json={"content": ""}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_content_field_returns_422(self, client, auth_headers, mock_fragment_enrich_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422


class TestFragmentEnrichSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_fragment_enrich_service):
        mock_fragment_enrich_service.enrich_fragment.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_summary_entities_topics(self, client, auth_headers, mock_fragment_enrich_service):
        mock_fragment_enrich_service.enrich_fragment.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "summary" in body
        assert "entities" in body
        assert "topics" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "fragment_enrich_service", None)
        try:
            if hasattr(app.state, "fragment_enrich_service"):
                delattr(app.state, "fragment_enrich_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.fragment_enrich_service = original
