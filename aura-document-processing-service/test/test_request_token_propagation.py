"""
Tests for the request-scoped bearer token propagation and the unified auth
error contract exposed by AuthenticationProviderMiddleware.
"""
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.infrastructure.http.authentication_provider.request_token import get_request_token

BY_DOCUMENTS_URL = "/api/v1/fragment-query/by-documents"
VALID_BY_DOCUMENTS_BODY = {"document_ids": [1, 2, 3]}


class TestRequestTokenPropagation:
    def test_token_is_visible_to_service_via_context_var(
        self, client, auth_headers, mock_fragment_query_service
    ):
        captured: dict[str, object] = {}

        async def _capture(*args, **kwargs):
            captured["token"] = get_request_token()
            return FragmentListResponse(fragments=[])

        mock_fragment_query_service.retrieve_context_fragments_by_documents.side_effect = _capture

        response = client.post(BY_DOCUMENTS_URL, json=VALID_BY_DOCUMENTS_BODY, headers=auth_headers)

        assert response.status_code == 200
        assert captured["token"] is not None
        assert str(captured["token"]).lower().startswith("bearer ")

    def test_token_matches_incoming_bearer(
        self, client, auth_headers, mock_fragment_query_service
    ):
        captured: dict[str, object] = {}

        async def _capture(*args, **kwargs):
            captured["token"] = get_request_token()
            return FragmentListResponse(fragments=[])

        mock_fragment_query_service.retrieve_context_fragments_by_documents.side_effect = _capture

        client.post(BY_DOCUMENTS_URL, json=VALID_BY_DOCUMENTS_BODY, headers=auth_headers)

        assert captured["token"] == auth_headers["Authorization"]


class TestAuthErrorContract:
    def test_missing_token_uses_unified_error_shape(self, client):
        response = client.post(BY_DOCUMENTS_URL, json=VALID_BY_DOCUMENTS_BODY)
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "missing_token"
        assert "message" in body
        assert "detail" not in body
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_uses_unified_error_shape(self, client):
        response = client.post(
            BY_DOCUMENTS_URL,
            json=VALID_BY_DOCUMENTS_BODY,
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert response.status_code == 401
        body = response.json()
        assert body["error"] == "invalid_token"
        assert "message" in body
        assert "detail" not in body
