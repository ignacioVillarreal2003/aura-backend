"""Unit tests for artifact endpoints + message artifact serialization (services mocked).

Endpoints covered:
  GET    /api/v1/artifacts/                  list user artifacts
  POST   /api/v1/artifacts/                  create artifact
  GET    /api/v1/artifacts/{id}/             get artifact
  PATCH  /api/v1/artifacts/{id}/             update artifact (bumps version)
  DELETE /api/v1/artifacts/{id}/             delete artifact
  GET    /api/v1/artifacts/{id}/versions/    list versions
  GET    /api/v1/artifacts/manage/           list all (admin)
"""
from apps.artifact.exceptions import ArtifactNotFoundException
from apps.message.serializers.response import MessageResponse
from test.conftest import make_artifact, make_artifact_version, make_message

VIEW = "apps.artifact.views"


# ── list / manage ─────────────────────────────────────────────────────────────

def test_list_artifacts_returns_200_paginated(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.list_artifacts", return_value=[make_artifact()])
    response = api_client.get("/api/v1/artifacts/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == 1


def test_list_artifacts_passes_filters_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.artifact_service.list_artifacts", return_value=[])
    api_client.get("/api/v1/artifacts/?chat_id=5&type=COURSE")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 5
    assert kwargs["artifact_type"] == "COURSE"


def test_list_artifacts_ignores_non_numeric_chat_id(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.artifact_service.list_artifacts", return_value=[])
    api_client.get("/api/v1/artifacts/?chat_id=abc")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] is None


def test_manage_artifacts_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.list_all_artifacts", return_value=[make_artifact()])
    response = api_client.get("/api/v1/artifacts/manage/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


# ── create ────────────────────────────────────────────────────────────────────

def test_create_artifact_returns_201(api_client, mocker):
    art = make_artifact(artifact_id=9, type="COURSE", title="Curso")
    svc = mocker.patch(f"{VIEW}.artifact_service.create_artifact", return_value=art)
    response = api_client.post("/api/v1/artifacts/", {"type": "COURSE", "title": "Curso"}, format="json")
    assert response.status_code == 201
    assert response.data["id"] == 9
    _, kwargs = svc.call_args
    assert kwargs["type"] == "COURSE"


def test_create_artifact_rejects_unknown_type(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.create_artifact")
    response = api_client.post("/api/v1/artifacts/", {"type": "NOPE", "title": "x"}, format="json")
    assert response.status_code == 400


def test_create_artifact_requires_title(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.create_artifact")
    response = api_client.post("/api/v1/artifacts/", {"type": "COURSE"}, format="json")
    assert response.status_code == 400


# ── get / patch / delete ──────────────────────────────────────────────────────

def test_get_artifact_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.get_artifact", return_value=make_artifact(artifact_id=3))
    response = api_client.get("/api/v1/artifacts/3/")
    assert response.status_code == 200
    assert response.data["id"] == 3


def test_get_artifact_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.get_artifact", side_effect=ArtifactNotFoundException())
    response = api_client.get("/api/v1/artifacts/77/")
    assert response.status_code == 404


def test_patch_artifact_returns_200(api_client, mocker):
    updated = make_artifact(artifact_id=3, version=2, title="Nuevo")
    svc = mocker.patch(f"{VIEW}.artifact_service.update_artifact", return_value=updated)
    response = api_client.patch("/api/v1/artifacts/3/", {"title": "Nuevo"}, format="json")
    assert response.status_code == 200
    assert response.data["version"] == 2
    _, kwargs = svc.call_args
    assert kwargs["title"] == "Nuevo"


def test_patch_artifact_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.artifact_service.update_artifact")
    response = api_client.patch("/api/v1/artifacts/3/", {}, format="json")
    assert response.status_code == 400


def test_delete_artifact_returns_204(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.artifact_service.delete_artifact")
    response = api_client.delete("/api/v1/artifacts/3/")
    assert response.status_code == 204
    svc.assert_called_once()


def test_list_versions_returns_200(api_client, mocker):
    mocker.patch(
        f"{VIEW}.artifact_service.list_versions",
        return_value=[make_artifact_version(version_number=1), make_artifact_version(version_id=2, version_number=2)],
    )
    response = api_client.get("/api/v1/artifacts/3/versions/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2


# ── message artifact serialization ────────────────────────────────────────────

def test_message_response_has_artifact_id_and_chat_id():
    msg = make_message(msg_id=1, artifact_id=5, chat_id=3)
    data = MessageResponse(msg).data
    assert data["artifact_id"] == 5
    assert data["chat_id"] == 3


def test_message_response_exposes_fragments_from_artifact():
    frags = [{"document": {"id": 1}, "content": "text"}]
    msg = make_message(msg_id=1)
    msg.artifact.fragments = frags
    data = MessageResponse(msg).data
    assert data["fragments"] == frags
