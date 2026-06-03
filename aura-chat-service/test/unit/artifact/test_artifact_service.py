"""Unit tests for the artifact service — all repository calls are mocked."""
import pytest

from apps.artifact.exceptions import (
    ArtifactAccessDeniedException,
    ArtifactNotFoundException,
    UnknownArtifactTypeException,
)
from apps.artifact.services.artifact_service import ArtifactService
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from test.conftest import make_artifact, make_artifact_version, make_user

SVC = "apps.artifact.services.artifact_service"

service = ArtifactService()


def _patch_access(mocker, *, artifact, is_member=False, is_contributor=False):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.artifact_repository.get_by_id", return_value=artifact)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=is_member)
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=is_contributor)


# ── get_artifact ──────────────────────────────────────────────────────────────

def test_get_artifact_creator_has_access(mocker):
    user = make_user(user_id=1)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, artifact=art)
    assert service.get_artifact(user, 1) is art


def test_get_artifact_active_member_has_access(mocker):
    user = make_user(user_id=2)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, artifact=art, is_member=True)
    assert service.get_artifact(user, 1) is art


def test_get_artifact_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, artifact=art, is_member=False)
    with pytest.raises(ArtifactAccessDeniedException):
        service.get_artifact(user, 1)


def test_get_artifact_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.artifact_repository.get_by_id", return_value=None)
    with pytest.raises(ArtifactNotFoundException):
        service.get_artifact(user, 99)


# ── create_artifact ───────────────────────────────────────────────────────────

def test_create_artifact_unknown_type_raises_400(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    with pytest.raises(UnknownArtifactTypeException):
        service.create_artifact(user, type="NOPE", title="x")


def test_create_artifact_success(mocker):
    user = make_user(user_id=1)
    art = make_artifact(artifact_id=5, type="COURSE", title="Curso")
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    create = mocker.patch(f"{SVC}.artifact_repository.create", return_value=art)
    result = service.create_artifact(user, type="COURSE", title="Curso")
    assert result is art
    _, kwargs = create.call_args
    assert kwargs["type"] == "COURSE"
    assert kwargs["user_id"] == 1


def test_create_artifact_with_chat_requires_contributor(mocker):
    user = make_user(user_id=2)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.create_artifact(user, type="REPORT", title="x", source_chat_id=10)


def test_create_artifact_missing_chat_raises_404(mocker):
    user = make_user(user_id=2)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.create_artifact(user, type="REPORT", title="x", source_chat_id=10)


# ── update_artifact ───────────────────────────────────────────────────────────

def test_update_artifact_creator_bumps_version(mocker):
    user = make_user(user_id=1)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10, version=1)
    _patch_access(mocker, artifact=art, is_contributor=True)
    updated = make_artifact(artifact_id=1, created_by=1, version=2, title="Nuevo")
    upd = mocker.patch(f"{SVC}.artifact_repository.update", return_value=updated)
    result = service.update_artifact(user, 1, title="Nuevo", change_summary="cambio")
    assert result.version == 2
    _, kwargs = upd.call_args
    assert kwargs["title"] == "Nuevo"
    assert kwargs["change_summary"] == "cambio"


def test_update_artifact_reader_member_forbidden(mocker):
    user = make_user(user_id=2)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10)
    # member but not contributor -> mutations denied
    _patch_access(mocker, artifact=art, is_member=True, is_contributor=False)
    with pytest.raises(ArtifactAccessDeniedException):
        service.update_artifact(user, 1, title="x")


def test_update_artifact_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.artifact_repository.get_by_id", return_value=None)
    with pytest.raises(ArtifactNotFoundException):
        service.update_artifact(user, 99, title="x")


# ── delete_artifact ───────────────────────────────────────────────────────────

def test_delete_artifact_creator_success(mocker):
    user = make_user(user_id=1)
    art = make_artifact(artifact_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, artifact=art, is_contributor=True)
    delete = mocker.patch(f"{SVC}.artifact_repository.soft_delete")
    service.delete_artifact(user, 1)
    delete.assert_called_once()


def test_delete_artifact_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.artifact_repository.get_by_id", return_value=None)
    with pytest.raises(ArtifactNotFoundException):
        service.delete_artifact(user, 99)


# ── list_artifacts / versions ─────────────────────────────────────────────────

def test_list_artifacts_unknown_type_raises_400(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    with pytest.raises(UnknownArtifactTypeException):
        service.list_artifacts(user, artifact_type="NOPE")


def test_list_artifacts_by_user(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    lst = mocker.patch(f"{SVC}.artifact_repository.list_by_user", return_value=[make_artifact()])
    result = service.list_artifacts(user)
    assert len(result) == 1
    lst.assert_called_once()


def test_list_versions_returns_history(mocker):
    user = make_user(user_id=1)
    art = make_artifact(artifact_id=1, created_by=1)
    _patch_access(mocker, artifact=art)
    mocker.patch(
        f"{SVC}.artifact_version_repository.list_for_artifact",
        return_value=[make_artifact_version(version_number=1), make_artifact_version(version_id=2, version_number=2)],
    )
    result = service.list_versions(user, 1)
    assert len(result) == 2
