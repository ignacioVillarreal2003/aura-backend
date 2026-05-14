import pytest

from core.exceptions.base import InsufficientPermissionsException
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    CollectionNotFoundException,
    CompartmentNotFoundException,
)
from test.conftest import make_document_collection

_SVC = "apps.document_collections.views.document_collection_viewset.document_collection_service"


# ---------------------------------------------------------------------------
# List  GET /api/v1/document-collections/
# ---------------------------------------------------------------------------

def test_list_document_collections_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collections", return_value=[make_document_collection()])
    response = api_client.get("/api/v1/document-collections/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_document_collections_empty(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collections", return_value=[])
    response = api_client.get("/api/v1/document-collections/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_document_collections_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/document-collections/")
    assert response.status_code == 401


def test_list_document_collections_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.list_document_collections", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/document-collections/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Create  POST /api/v1/document-collections/
# ---------------------------------------------------------------------------

def test_create_document_collection_returns_201(api_client, mocker):
    collection = make_document_collection(name="Alpha Docs")
    mocker.patch(f"{_SVC}.create_document_collection", return_value=collection)
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Alpha Docs", "classification_level_id": 1, "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["name"] == "Alpha Docs"


def test_create_document_collection_passes_fields_to_service(api_client, mocker):
    collection = make_document_collection()
    svc = mocker.patch(f"{_SVC}.create_document_collection", return_value=collection)
    api_client.post(
        "/api/v1/document-collections/",
        {"name": "My Docs", "classification_level_id": 2, "compartment_ids": [3, 4]},
        format="json",
    )
    svc.assert_called_once()
    _, kwargs = svc.call_args
    assert kwargs["name"] == "My Docs"
    assert kwargs["classification_level_id"] == 2
    assert set(kwargs["compartment_ids"]) == {3, 4}


def test_create_document_collection_missing_name_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection")
    response = api_client.post(
        "/api/v1/document-collections/",
        {"classification_level_id": 1, "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 400


def test_create_document_collection_missing_classification_level_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection")
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 400


def test_create_document_collection_empty_compartment_ids_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection")
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "classification_level_id": 1, "compartment_ids": []},
        format="json",
    )
    assert response.status_code == 400


def test_create_document_collection_classification_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection", side_effect=ClassificationLevelNotFoundException())
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "classification_level_id": 99, "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"] == "classification_level_not_found"


def test_create_document_collection_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection", side_effect=CompartmentNotFoundException())
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "classification_level_id": 1, "compartment_ids": [999]},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"] == "compartment_not_found"


def test_create_document_collection_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.create_document_collection", side_effect=InsufficientPermissionsException())
    response = api_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "classification_level_id": 1, "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 403


def test_create_document_collection_unauthenticated(anon_client):
    response = anon_client.post(
        "/api/v1/document-collections/",
        {"name": "Test", "classification_level_id": 1, "compartment_ids": [1]},
        format="json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Retrieve  GET /api/v1/document-collections/{id}/
# ---------------------------------------------------------------------------

def test_retrieve_document_collection_returns_200(api_client, mocker):
    collection = make_document_collection(collection_id=5, name="Classified Ops")
    mocker.patch(f"{_SVC}.get_document_collection", return_value=collection)
    response = api_client.get("/api/v1/document-collections/5/")
    assert response.status_code == 200
    assert response.data["id"] == 5
    assert response.data["name"] == "Classified Ops"


def test_retrieve_document_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.get_document_collection", side_effect=CollectionNotFoundException())
    response = api_client.get("/api/v1/document-collections/99/")
    assert response.status_code == 404
    assert response.data["error"] == "document_collection_not_found"


def test_retrieve_document_collection_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.get_document_collection", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/document-collections/1/")
    assert response.status_code == 403


def test_retrieve_document_collection_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/document-collections/1/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Partial update  PATCH /api/v1/document-collections/{id}/
# ---------------------------------------------------------------------------

def test_update_document_collection_name_returns_200(api_client, mocker):
    collection = make_document_collection(name="Renamed Collection")
    mocker.patch(f"{_SVC}.update_document_collection", return_value=collection)
    response = api_client.patch(
        "/api/v1/document-collections/1/",
        {"name": "Renamed Collection"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Renamed Collection"


def test_update_document_collection_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.update_document_collection")
    response = api_client.patch("/api/v1/document-collections/1/", {}, format="json")
    assert response.status_code == 400


def test_update_document_collection_empty_compartment_ids_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.update_document_collection")
    response = api_client.patch(
        "/api/v1/document-collections/1/",
        {"compartment_ids": []},
        format="json",
    )
    assert response.status_code == 400


def test_update_document_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.update_document_collection", side_effect=CollectionNotFoundException())
    response = api_client.patch("/api/v1/document-collections/99/", {"name": "X"}, format="json")
    assert response.status_code == 404


def test_update_document_collection_classification_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{_SVC}.update_document_collection",
        side_effect=ClassificationLevelNotFoundException(),
    )
    response = api_client.patch(
        "/api/v1/document-collections/1/",
        {"classification_level_id": 99},
        format="json",
    )
    assert response.status_code == 404


def test_update_document_collection_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.update_document_collection", side_effect=CompartmentNotFoundException())
    response = api_client.patch(
        "/api/v1/document-collections/1/",
        {"compartment_ids": [999]},
        format="json",
    )
    assert response.status_code == 404


def test_update_document_collection_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.update_document_collection", side_effect=InsufficientPermissionsException())
    response = api_client.patch("/api/v1/document-collections/1/", {"name": "X"}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Destroy  DELETE /api/v1/document-collections/{id}/
# ---------------------------------------------------------------------------

def test_destroy_document_collection_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_document_collection", return_value=None)
    response = api_client.delete("/api/v1/document-collections/1/")
    assert response.status_code == 204


def test_destroy_document_collection_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_document_collection", side_effect=CollectionNotFoundException())
    response = api_client.delete("/api/v1/document-collections/99/")
    assert response.status_code == 404


def test_destroy_document_collection_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_document_collection", side_effect=InsufficientPermissionsException())
    response = api_client.delete("/api/v1/document-collections/1/")
    assert response.status_code == 403


def test_destroy_document_collection_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/document-collections/1/")
    assert response.status_code == 401
