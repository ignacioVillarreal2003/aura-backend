"""
Tests for:
  POST /api/v1/fragment-query/by-question
  POST /api/v1/fragment-query/by-documents
"""
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse

BY_QUESTION_URL = "/api/v1/fragment-query/by-question"
BY_DOCUMENTS_URL = "/api/v1/fragment-query/by-documents"

VALID_BY_QUESTION_BODY = {
    "semantic_queries": [{"text": "cláusulas de rescisión", "max_fragments": 5}],
}

VALID_BY_DOCUMENTS_BODY = {
    "document_ids": [1, 2, 3],
}

_RESPONSE = FragmentListResponse(fragments=[])


class TestFragmentQueryAuth:
    def test_by_question_missing_auth_returns_401(self, client):
        assert client.post(BY_QUESTION_URL, json=VALID_BY_QUESTION_BODY).status_code == 401

    def test_by_documents_missing_auth_returns_401(self, client):
        assert client.post(BY_DOCUMENTS_URL, json=VALID_BY_DOCUMENTS_BODY).status_code == 401


class TestFragmentQueryValidation:
    def test_by_documents_empty_ids_returns_422(self, client, auth_headers, mock_fragment_query_service):
        response = client.post(BY_DOCUMENTS_URL, json={"document_ids": []}, headers=auth_headers)
        assert response.status_code == 422

    def test_by_documents_duplicate_ids_returns_422(self, client, auth_headers, mock_fragment_query_service):
        response = client.post(BY_DOCUMENTS_URL, json={"document_ids": [1, 1]}, headers=auth_headers)
        assert response.status_code == 422

    def test_by_documents_zero_id_returns_422(self, client, auth_headers, mock_fragment_query_service):
        response = client.post(BY_DOCUMENTS_URL, json={"document_ids": [0]}, headers=auth_headers)
        assert response.status_code == 422

    def test_by_question_empty_semantic_query_text_returns_422(self, client, auth_headers, mock_fragment_query_service):
        body = {"semantic_queries": [{"text": "", "max_fragments": 5}]}
        response = client.post(BY_QUESTION_URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_by_question_max_fragments_zero_returns_422(self, client, auth_headers, mock_fragment_query_service):
        body = {"semantic_queries": [{"text": "query", "max_fragments": 0}]}
        response = client.post(BY_QUESTION_URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestFragmentQuerySuccess:
    def test_by_question_returns_200(self, client, auth_headers, mock_fragment_query_service):
        mock_fragment_query_service.retrieve_context_fragments_by_question.return_value = _RESPONSE
        response = client.post(BY_QUESTION_URL, json=VALID_BY_QUESTION_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_by_question_response_has_fragments_key(self, client, auth_headers, mock_fragment_query_service):
        mock_fragment_query_service.retrieve_context_fragments_by_question.return_value = _RESPONSE
        body = client.post(BY_QUESTION_URL, json=VALID_BY_QUESTION_BODY, headers=auth_headers).json()
        assert "fragments" in body
        assert isinstance(body["fragments"], list)

    def test_by_documents_returns_200(self, client, auth_headers, mock_fragment_query_service):
        mock_fragment_query_service.retrieve_context_fragments_by_documents.return_value = _RESPONSE
        response = client.post(BY_DOCUMENTS_URL, json=VALID_BY_DOCUMENTS_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_by_question_with_bm25_queries(self, client, auth_headers, mock_fragment_query_service):
        mock_fragment_query_service.retrieve_context_fragments_by_question.return_value = _RESPONSE
        body = {
            "semantic_queries": [{"text": "penalidades", "max_fragments": 3}],
            "bm25_queries": [{"text": "penalidades contractuales", "max_fragments": 3}],
        }
        response = client.post(BY_QUESTION_URL, json=body, headers=auth_headers)
        assert response.status_code == 200

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "fragment_query_service", None)
        try:
            if hasattr(app.state, "fragment_query_service"):
                delattr(app.state, "fragment_query_service")
            assert client.post(BY_QUESTION_URL, json=VALID_BY_QUESTION_BODY, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.fragment_query_service = original
