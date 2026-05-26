import pytest

from core.exceptions.base import InsufficientPermissionsException
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    DuplicateClassificationLevelException,
    ClassificationLevelInUseException,
)
from test.conftest import make_classification_level

_SVC = "apps.classification_levels.views.classification_level_viewset.classification_level_service"


# ---------------------------------------------------------------------------
# List  GET /api/v1/classification-levels/
# ---------------------------------------------------------------------------

def test_list_classification_levels_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.list_classification_levels", return_value=[make_classification_level()])
    response = api_client.get("/api/v1/classification-levels/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_classification_levels_empty(api_client, mocker):
    mocker.patch(f"{_SVC}.list_classification_levels", return_value=[])
    response = api_client.get("/api/v1/classification-levels/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_classification_levels_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/classification-levels/")
    assert response.status_code == 401


def test_list_classification_levels_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.list_classification_levels", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/classification-levels/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Create  POST /api/v1/classification-levels/
# ---------------------------------------------------------------------------

def test_create_classification_level_returns_201(api_client, mocker):
    level = make_classification_level()
    mocker.patch(f"{_SVC}.create_classification_level", return_value=level)
    response = api_client.post(
        "/api/v1/classification-levels/",
        {"name": "TOP SECRET", "rank": 5},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["name"] == "TOP SECRET"


def test_create_classification_level_missing_name_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level")
    response = api_client.post("/api/v1/classification-levels/", {"rank": 5}, format="json")
    assert response.status_code == 400


def test_create_classification_level_missing_rank_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level")
    response = api_client.post("/api/v1/classification-levels/", {"name": "SECRET"}, format="json")
    assert response.status_code == 400


def test_create_classification_level_whitespace_name_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level")
    response = api_client.post("/api/v1/classification-levels/", {"name": "   ", "rank": 1}, format="json")
    assert response.status_code == 400


def test_create_classification_level_rank_zero_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level")
    response = api_client.post("/api/v1/classification-levels/", {"name": "X", "rank": 0}, format="json")
    assert response.status_code == 400


def test_create_classification_level_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level", side_effect=DuplicateClassificationLevelException())
    response = api_client.post(
        "/api/v1/classification-levels/",
        {"name": "TOP SECRET", "rank": 5},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"] == "duplicate_classification_level"


def test_create_classification_level_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.create_classification_level", side_effect=InsufficientPermissionsException())
    response = api_client.post(
        "/api/v1/classification-levels/",
        {"name": "SECRET", "rank": 3},
        format="json",
    )
    assert response.status_code == 403


def test_create_classification_level_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/classification-levels/", {"name": "X", "rank": 1}, format="json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Retrieve  GET /api/v1/classification-levels/{id}/
# ---------------------------------------------------------------------------

def test_retrieve_classification_level_returns_200(api_client, mocker):
    level = make_classification_level(level_id=3, name="CONFIDENTIAL", rank=3)
    mocker.patch(f"{_SVC}.get_classification_level", return_value=level)
    response = api_client.get("/api/v1/classification-levels/3/")
    assert response.status_code == 200
    assert response.data["id"] == 3
    assert response.data["name"] == "CONFIDENTIAL"


def test_retrieve_classification_level_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.get_classification_level", side_effect=ClassificationLevelNotFoundException())
    response = api_client.get("/api/v1/classification-levels/99/")
    assert response.status_code == 404
    assert response.data["error"] == "classification_level_not_found"


def test_retrieve_classification_level_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.get_classification_level", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/classification-levels/1/")
    assert response.status_code == 403


def test_retrieve_classification_level_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/classification-levels/1/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Partial update  PATCH /api/v1/classification-levels/{id}/
# ---------------------------------------------------------------------------

def test_update_classification_level_returns_200(api_client, mocker):
    level = make_classification_level(name="RENAMED", rank=7)
    mocker.patch(f"{_SVC}.update_classification_level", return_value=level)
    response = api_client.patch("/api/v1/classification-levels/1/", {"name": "RENAMED"}, format="json")
    assert response.status_code == 200
    assert response.data["name"] == "RENAMED"


def test_update_classification_level_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.update_classification_level")
    response = api_client.patch("/api/v1/classification-levels/1/", {}, format="json")
    assert response.status_code == 400


def test_update_classification_level_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.update_classification_level", side_effect=ClassificationLevelNotFoundException())
    response = api_client.patch("/api/v1/classification-levels/99/", {"rank": 2}, format="json")
    assert response.status_code == 404


def test_update_classification_level_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.update_classification_level", side_effect=DuplicateClassificationLevelException())
    response = api_client.patch("/api/v1/classification-levels/1/", {"name": "EXISTING"}, format="json")
    assert response.status_code == 409


def test_update_classification_level_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.update_classification_level", side_effect=InsufficientPermissionsException())
    response = api_client.patch("/api/v1/classification-levels/1/", {"rank": 2}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Destroy  DELETE /api/v1/classification-levels/{id}/
# ---------------------------------------------------------------------------

def test_destroy_classification_level_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_classification_level", return_value=None)
    response = api_client.delete("/api/v1/classification-levels/1/")
    assert response.status_code == 204


def test_destroy_classification_level_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_classification_level", side_effect=ClassificationLevelNotFoundException())
    response = api_client.delete("/api/v1/classification-levels/99/")
    assert response.status_code == 404


def test_destroy_classification_level_in_use_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_classification_level", side_effect=ClassificationLevelInUseException())
    response = api_client.delete("/api/v1/classification-levels/1/")
    assert response.status_code == 409
    assert response.data["error"] == "classification_level_in_use"


def test_destroy_classification_level_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_classification_level", side_effect=InsufficientPermissionsException())
    response = api_client.delete("/api/v1/classification-levels/1/")
    assert response.status_code == 403


def test_destroy_classification_level_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/classification-levels/1/")
    assert response.status_code == 401
