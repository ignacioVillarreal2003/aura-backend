"""
Tests for POST /api/v1/fragment-contextualize
"""
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)

URL = "/api/v1/fragment-contextualize"

VALID_BODY = {
    "document_summary": "Contrato de servicios entre Acme S.A. y un proveedor, año 2024.",
    "content": "La empresa Acme S.A. firmó un contrato el 10 de enero de 2024.",
}

_RESPONSE = ContextualizeFragmentResponse(
    context="Fragmento de la sección de antecedentes del contrato de Acme S.A. de 2024.",
)


class TestFragmentContextualizeAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_fragment_contextualize_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_fragment_contextualize_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestFragmentContextualizeValidation:
    def test_blank_content_returns_422(self, client, auth_headers, mock_fragment_contextualize_service):
        body = {**VALID_BODY, "content": "  "}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_content_field_returns_422(self, client, auth_headers, mock_fragment_contextualize_service):
        response = client.post(URL, json={"document_summary": "x"}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_document_summary_returns_422(self, client, auth_headers, mock_fragment_contextualize_service):
        response = client.post(URL, json={"content": "texto"}, headers=auth_headers)
        assert response.status_code == 422


class TestFragmentContextualizeSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_fragment_contextualize_service):
        mock_fragment_contextualize_service.contextualize_fragment.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_context(self, client, auth_headers, mock_fragment_contextualize_service):
        mock_fragment_contextualize_service.contextualize_fragment.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "context" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "fragment_contextualize_service", None)
        try:
            if hasattr(app.state, "fragment_contextualize_service"):
                delattr(app.state, "fragment_contextualize_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.fragment_contextualize_service = original
