import pytest

from core.exceptions.base import InsufficientPermissionsException
from core.domain.document_collection_exceptions import (
    ClassificationLevelNotFoundException,
    CompartmentNotFoundException,
    UserClearanceNotFoundException,
    UserCompartmentNotFoundException,
    DuplicateUserCompartmentException,
)
from test.conftest import (
    make_user_clearance,
    make_user_compartment,
    make_document_collection,
)

_SVC = "apps.user_authorizations.views.user_authorization_viewset.user_authorization_service"

_USER_URL = "/api/v1/user-authorizations/10/"
_CLEARANCE_URL = "/api/v1/user-authorizations/10/clearance/"
_COMPARTMENTS_URL = "/api/v1/user-authorizations/10/compartments/"
_REMOVE_COMPARTMENT_URL = "/api/v1/user-authorizations/10/compartments/2/"
_ACCESSIBLE_URL = "/api/v1/user-authorizations/10/accessible-collections/"


# ---------------------------------------------------------------------------
# Retrieve  GET /api/v1/user-authorizations/{user_id}/
# ---------------------------------------------------------------------------

def test_retrieve_user_authorization_returns_200(api_client, mocker):
    data = {"user_id": 10, "clearance": make_user_clearance(), "compartments": [make_user_compartment()]}
    mocker.patch(f"{_SVC}.get_user_authorization", return_value=data)
    response = api_client.get(_USER_URL)
    assert response.status_code == 200


def test_retrieve_user_authorization_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.get_user_authorization", side_effect=InsufficientPermissionsException())
    response = api_client.get(_USER_URL)
    assert response.status_code == 403


def test_retrieve_user_authorization_unauthenticated(anon_client):
    response = anon_client.get(_USER_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Set clearance  PUT /api/v1/user-authorizations/{user_id}/clearance/
# ---------------------------------------------------------------------------

def test_set_clearance_returns_200(api_client, mocker):
    clearance = make_user_clearance()
    mocker.patch(f"{_SVC}.set_user_clearance", return_value=clearance)
    response = api_client.put(_CLEARANCE_URL, {"classification_level_id": 1}, format="json")
    assert response.status_code == 200


def test_set_clearance_missing_body_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.set_user_clearance")
    response = api_client.put(_CLEARANCE_URL, {}, format="json")
    assert response.status_code == 400


def test_set_clearance_level_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.set_user_clearance", side_effect=ClassificationLevelNotFoundException())
    response = api_client.put(_CLEARANCE_URL, {"classification_level_id": 99}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "classification_level_not_found"


def test_set_clearance_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.set_user_clearance", side_effect=InsufficientPermissionsException())
    response = api_client.put(_CLEARANCE_URL, {"classification_level_id": 1}, format="json")
    assert response.status_code == 403


def test_set_clearance_unauthenticated(anon_client):
    response = anon_client.put(_CLEARANCE_URL, {"classification_level_id": 1}, format="json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Delete clearance  DELETE /api/v1/user-authorizations/{user_id}/clearance/
# ---------------------------------------------------------------------------

def test_delete_clearance_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_user_clearance", return_value=None)
    response = api_client.delete(_CLEARANCE_URL)
    assert response.status_code == 204


def test_delete_clearance_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_user_clearance", side_effect=UserClearanceNotFoundException())
    response = api_client.delete(_CLEARANCE_URL)
    assert response.status_code == 404
    assert response.data["error"] == "user_clearance_not_found"


def test_delete_clearance_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_user_clearance", side_effect=InsufficientPermissionsException())
    response = api_client.delete(_CLEARANCE_URL)
    assert response.status_code == 403


def test_delete_clearance_unauthenticated(anon_client):
    response = anon_client.delete(_CLEARANCE_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List compartments  GET /api/v1/user-authorizations/{user_id}/compartments/
# ---------------------------------------------------------------------------

def test_list_compartments_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.list_user_compartments", return_value=[make_user_compartment()])
    response = api_client.get(_COMPARTMENTS_URL)
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_compartments_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.list_user_compartments", side_effect=InsufficientPermissionsException())
    response = api_client.get(_COMPARTMENTS_URL)
    assert response.status_code == 403


def test_list_compartments_unauthenticated(anon_client):
    response = anon_client.get(_COMPARTMENTS_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Add compartment  POST /api/v1/user-authorizations/{user_id}/compartments/
# ---------------------------------------------------------------------------

def test_add_compartment_returns_201(api_client, mocker):
    uc = make_user_compartment()
    mocker.patch(f"{_SVC}.add_user_compartment", return_value=uc)
    response = api_client.post(_COMPARTMENTS_URL, {"compartment_id": 1}, format="json")
    assert response.status_code == 201


def test_add_compartment_missing_body_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.add_user_compartment")
    response = api_client.post(_COMPARTMENTS_URL, {}, format="json")
    assert response.status_code == 400


def test_add_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.add_user_compartment", side_effect=CompartmentNotFoundException())
    response = api_client.post(_COMPARTMENTS_URL, {"compartment_id": 99}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "compartment_not_found"


def test_add_compartment_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.add_user_compartment", side_effect=DuplicateUserCompartmentException())
    response = api_client.post(_COMPARTMENTS_URL, {"compartment_id": 1}, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "duplicate_user_compartment"


def test_add_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.add_user_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.post(_COMPARTMENTS_URL, {"compartment_id": 1}, format="json")
    assert response.status_code == 403


def test_add_compartment_unauthenticated(anon_client):
    response = anon_client.post(_COMPARTMENTS_URL, {"compartment_id": 1}, format="json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Remove compartment  DELETE /api/v1/user-authorizations/{user_id}/compartments/{id}/
# ---------------------------------------------------------------------------

def test_remove_compartment_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_user_compartment", return_value=None)
    response = api_client.delete(_REMOVE_COMPARTMENT_URL)
    assert response.status_code == 204


def test_remove_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_user_compartment", side_effect=UserCompartmentNotFoundException())
    response = api_client.delete(_REMOVE_COMPARTMENT_URL)
    assert response.status_code == 404
    assert response.data["error"] == "user_compartment_not_found"


def test_remove_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.remove_user_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.delete(_REMOVE_COMPARTMENT_URL)
    assert response.status_code == 403


def test_remove_compartment_unauthenticated(anon_client):
    response = anon_client.delete(_REMOVE_COMPARTMENT_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Accessible collections  GET /api/v1/user-authorizations/{user_id}/accessible-collections/
# ---------------------------------------------------------------------------

def test_accessible_collections_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.get_accessible_collections", return_value=[make_document_collection()])
    response = api_client.get(_ACCESSIBLE_URL)
    assert response.status_code == 200
    assert "results" in response.data


def test_accessible_collections_empty(api_client, mocker):
    mocker.patch(f"{_SVC}.get_accessible_collections", return_value=[])
    response = api_client.get(_ACCESSIBLE_URL)
    assert response.status_code == 200
    assert response.data["results"] == []


def test_accessible_collections_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.get_accessible_collections", side_effect=InsufficientPermissionsException())
    response = api_client.get(_ACCESSIBLE_URL)
    assert response.status_code == 403


def test_accessible_collections_unauthenticated(anon_client):
    response = anon_client.get(_ACCESSIBLE_URL)
    assert response.status_code == 401
