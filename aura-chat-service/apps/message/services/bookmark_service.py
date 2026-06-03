from apps.artifact.models.artifact import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.repositories.bookmark_repository import bookmark_repository
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import BOOKMARK_MESSAGE, LIST_BOOKMARKS


def _require_artifact_access(user_id: int, chat_id: int, artifact_id: int) -> Artifact:
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    artifact = artifact_repository.get_by_id(artifact_id)
    if artifact is None or artifact.source_chat_id != chat_id:
        raise MessageNotFoundException()
    return artifact


class BookmarkService:
    def bookmark(self, user: AuthenticatedUser, chat_id: int, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({BOOKMARK_MESSAGE}))
        _require_artifact_access(user.id, chat_id, artifact_id)
        bookmark_repository.create(artifact_id=artifact_id, user_id=user.id)

    def unbookmark(self, user: AuthenticatedUser, chat_id: int, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({BOOKMARK_MESSAGE}))
        _require_artifact_access(user.id, chat_id, artifact_id)
        bookmark_repository.delete(artifact_id=artifact_id, user_id=user.id)

    def list_bookmarked(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({LIST_BOOKMARKS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        ids = bookmark_repository.get_bookmarked_artifact_ids(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id).filter(
            artifact_id__in=ids
        )


bookmark_service = BookmarkService()
