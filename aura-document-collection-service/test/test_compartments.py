import pytest

from core.exceptions.base import InsufficientPermissionsException
from core.domain.document_collection_exceptions import (
    CompartmentNotFoundException,
    DuplicateCompartmentException,
    CompartmentInUseException,
)
from test.conftest import make_compartment

_SVC = "apps.compartments.views.compartment_viewset.compartment_service"


# ---------------------------------------------------------------------------
# List  GET /api/v1/compartments/
# ---------------------------------------------------------------------------

def test_list_compartments_returns_200(api_client, mocker):
    mocker.patch(f"{_SVC}.list_compartments", return_value=[make_compartment()])
    response = api_client.get("/api/v1/compartments/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_compartments_empty(api_client, mocker):
    mocker.patch(f"{_SVC}.list_compartments", return_value=[])
    response = api_client.get("/api/v1/compartments/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_compartments_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/compartments/")
    assert response.status_code == 401


def test_list_compartments_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.list_compartments", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/compartments/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Create  POST /api/v1/compartments/
# ---------------------------------------------------------------------------

def test_create_compartment_returns_201(api_client, mocker):
    compartment = make_compartment(name="BRAVO", description="Bravo unit")
    mocker.patch(f"{_SVC}.create_compartment", return_value=compartment)
    response = api_client.post(
        "/api/v1/compartments/",
        {"name": "BRAVO", "description": "Bravo unit"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["name"] == "BRAVO"


def test_create_compartment_without_description_returns_201(api_client, mocker):
    compartment = make_compartment(name="CHARLIE", description="")
    mocker.patch(f"{_SVC}.create_compartment", return_value=compartment)
    response = api_client.post("/api/v1/compartments/", {"name": "CHARLIE"}, format="json")
    assert response.status_code == 201


def test_create_compartment_missing_name_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_compartment")
    response = api_client.post("/api/v1/compartments/", {"description": "no name"}, format="json")
    assert response.status_code == 400


def test_create_compartment_whitespace_name_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.create_compartment")
    response = api_client.post("/api/v1/compartments/", {"name": "   "}, format="json")
    assert response.status_code == 400


def test_create_compartment_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.create_compartment", side_effect=DuplicateCompartmentException())
    response = api_client.post("/api/v1/compartments/", {"name": "ALPHA"}, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "duplicate_compartment"


def test_create_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.create_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.post("/api/v1/compartments/", {"name": "DELTA"}, format="json")
    assert response.status_code == 403


def test_create_compartment_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/compartments/", {"name": "ECHO"}, format="json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Retrieve  GET /api/v1/compartments/{id}/
# ---------------------------------------------------------------------------

def test_retrieve_compartment_returns_200(api_client, mocker):
    compartment = make_compartment(compartment_id=2, name="FOXTROT")
    mocker.patch(f"{_SVC}.get_compartment", return_value=compartment)
    response = api_client.get("/api/v1/compartments/2/")
    assert response.status_code == 200
    assert response.data["id"] == 2
    assert response.data["name"] == "FOXTROT"


def test_retrieve_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.get_compartment", side_effect=CompartmentNotFoundException())
    response = api_client.get("/api/v1/compartments/99/")
    assert response.status_code == 404
    assert response.data["error"] == "compartment_not_found"


def test_retrieve_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.get_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/compartments/1/")
    assert response.status_code == 403


def test_retrieve_compartment_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/compartments/1/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Partial update  PATCH /api/v1/compartments/{id}/
# ---------------------------------------------------------------------------

def test_update_compartment_returns_200(api_client, mocker):
    compartment = make_compartment(name="RENAMED")
    mocker.patch(f"{_SVC}.update_compartment", return_value=compartment)
    response = api_client.patch("/api/v1/compartments/1/", {"name": "RENAMED"}, format="json")
    assert response.status_code == 200
    assert response.data["name"] == "RENAMED"


def test_update_compartment_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{_SVC}.update_compartment")
    response = api_client.patch("/api/v1/compartments/1/", {}, format="json")
    assert response.status_code == 400


def test_update_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.update_compartment", side_effect=CompartmentNotFoundException())
    response = api_client.patch("/api/v1/compartments/99/", {"name": "X"}, format="json")
    assert response.status_code == 404


def test_update_compartment_duplicate_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.update_compartment", side_effect=DuplicateCompartmentException())
    response = api_client.patch("/api/v1/compartments/1/", {"name": "EXISTING"}, format="json")
    assert response.status_code == 409


def test_update_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.update_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.patch("/api/v1/compartments/1/", {"description": "new desc"}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Destroy  DELETE /api/v1/compartments/{id}/
# ---------------------------------------------------------------------------

def test_destroy_compartment_returns_204(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_compartment", return_value=None)
    response = api_client.delete("/api/v1/compartments/1/")
    assert response.status_code == 204


def test_destroy_compartment_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_compartment", side_effect=CompartmentNotFoundException())
    response = api_client.delete("/api/v1/compartments/99/")
    assert response.status_code == 404


def test_destroy_compartment_in_use_returns_409(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_compartment", side_effect=CompartmentInUseException())
    response = api_client.delete("/api/v1/compartments/1/")
    assert response.status_code == 409
    assert response.data["error"] == "compartment_in_use"


def test_destroy_compartment_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{_SVC}.delete_compartment", side_effect=InsufficientPermissionsException())
    response = api_client.delete("/api/v1/compartments/1/")
    assert response.status_code == 403


def test_destroy_compartment_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/compartments/1/")
    assert response.status_code == 401
