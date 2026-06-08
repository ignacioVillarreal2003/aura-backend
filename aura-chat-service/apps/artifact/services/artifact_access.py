from apps.artifact.exceptions import ArtifactAccessDeniedException, ArtifactNotFoundException
from apps.artifact.models.artifact import Artifact
from apps.membership.repositories.membership_repository import membership_repository


def assert_detail_access(
        user_id: int,
        obj,
        access_denied_exc: Exception,
        *,
        require_contributor: bool = False,
) -> None:
    if obj.created_by == user_id:
        return
    source_chat_id = obj.artifact.source_chat_id
    checker = (
        membership_repository.is_active_contributor
        if require_contributor
        else membership_repository.is_active_member
    )
    if checker(source_chat_id, user_id):
        return
    raise access_denied_exc


def require_interaction_access(user_id: int, artifact_id: int) -> Artifact:
    from apps.artifact.repositories.artifact_repository import artifact_repository

    artifact = artifact_repository.get_by_id(artifact_id)
    if artifact is None:
        raise ArtifactNotFoundException()
    if artifact.created_by == user_id:
        return artifact
    if not membership_repository.is_active_member(artifact.source_chat_id, user_id):
        raise ArtifactAccessDeniedException()
    return artifact
