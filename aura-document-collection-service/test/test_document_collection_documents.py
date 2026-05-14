import pytest

from core.exceptions.base import InsufficientPermissionsException
from core.domain.document_collection_exceptions import (
    CollectionNotFoundException,
    DocumentLinkNotFoundException,
    DocumentNotAvailableException,
    DuplicateDocumentLinkException,
)
from test.conftest import make_document_link

_SVC = "apps.document_collection_documents.views.document_collection_document_viewset.document_collection_document_service"

_LIST_URL = "/api/v1/document-collections/1/documents/"
_CREATE_URL = "/api/v1/document-collections/1/documents/"
_DESTROY_URL = "/api/v1/document-collections/1/documents/5/"


# ---------------------------------------------------------------------------
# List  GET /api/v1/document-collections/{pk}/documents/
# ---------------------------------------------------------------------------

def test_list_documents_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collection_documents", return_value=[make_document_link()])
    response = api_client.get(_LIST_URL)
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_documents_empty(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collection_documents", return_value=[])
    response = api_client.get(_LIST_URL)
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_documents_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collection_documents", side_effect=CollectionNotFoundException())
    response = api_client.get(_LIST_URL)
    assert response.status_code == 404
    assert response.data["error"] == "document_collection_not_found"


def test_list_documents_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collection_documents", side_effect=InsufficientPermissionsException())
    response = api_client.get(_LIST_URL)
    assert response.status_code == 403


def test_list_documents_unauthenticated(anon_client):
    response = anon_client.get(_LIST_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Create  POST /api/v1/document-collections/{pk}/documents/
# ---------------------------------------------------------------------------

def test_add_document_returns_201(api_client, mocker):
    link = make_document_link(document_id=5)
    mocker.patch(f"{_SVC}.add_document_collection_document", return_value=link)
    response = api_client.post(_CREATE_URL, {"document_id": 5}, format="json")
    assert response.status_code == 201


def test_add_document_passes_ids_to_service(api_client, mocker):
    link = make_document_link()
    svc = mocker.patch(f"{_SVC}.add_document_collection_document", return_value=link)
    api_client.post(_CREATE_URL, {"document_id": 7}, format="json")
    svc.assert_called_once()
    _, kwargs = svc.call_args
    assert kwargs["document_id"] == 7


def test_add_document_missing_document_id_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.add_document_collection_document")
    response = api_client.post(_CREATE_URL, {}, format="json")
    assert response.status_code == 400


def test_add_document_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.add_document_collection_document", side_effect=CollectionNotFoundException())
    response = api_client.post(_CREATE_URL, {"document_id": 1}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "document_collection_not_found"


def test_add_document_not_available_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.add_document_collection_document", side_effect=DocumentNotAvailableException())
    response = api_client.post(_CREATE_URL, {"document_id": 99}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "document_not_available"


def test_add_document_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.add_document_collection_document", side_effect=DuplicateDocumentLinkException())
    response = api_client.post(_CREATE_URL, {"document_id": 5}, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "duplicate_document_link"


def test_add_document_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.add_document_collection_document", side_effect=InsufficientPermissionsException())
    response = api_client.post(_CREATE_URL, {"document_id": 1}, format="json")
    assert response.status_code == 403


def test_add_document_unauthenticated(anon_client):
    response = anon_client.post(_CREATE_URL, {"document_id": 1}, format="json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Destroy  DELETE /api/v1/document-collections/{pk}/documents/{pk}/
# ---------------------------------------------------------------------------

def test_remove_document_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_document_collection_document", return_value=None)
    response = api_client.delete(_DESTROY_URL)
    assert response.status_code == 204


def test_remove_document_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_document_collection_document", side_effect=CollectionNotFoundException())
    response = api_client.delete(_DESTROY_URL)
    assert response.status_code == 404


def test_remove_document_link_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_document_collection_document", side_effect=DocumentLinkNotFoundException())
    response = api_client.delete(_DESTROY_URL)
    assert response.status_code == 404
    assert response.data["error"] == "document_link_not_found"


def test_remove_document_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_document_collection_document", side_effect=InsufficientPermissionsException())
    response = api_client.delete(_DESTROY_URL)
    assert response.status_code == 403


def test_remove_document_unauthenticated(anon_client):
    response = anon_client.delete(_DESTROY_URL)
    assert response.status_code == 401
