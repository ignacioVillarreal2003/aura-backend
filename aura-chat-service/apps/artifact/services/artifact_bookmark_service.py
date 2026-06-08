from django.db.models import QuerySet

from apps.artifact.models.artifact import Artifact
from apps.artifact.repositories.artifact_bookmark_repository import bookmark_repository
from apps.artifact.services.artifact_access import require_interaction_access
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import BOOKMARK_MESSAGE, LIST_BOOKMARKS


class BookmarkService:
    def bookmark(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({BOOKMARK_MESSAGE}))
        require_interaction_access(user.id, artifact_id)
        bookmark_repository.create(artifact_id=artifact_id, user_id=user.id)

    def unbookmark(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({BOOKMARK_MESSAGE}))
        require_interaction_access(user.id, artifact_id)
        bookmark_repository.delete(artifact_id=artifact_id, user_id=user.id)

    def list_bookmarked(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[Artifact]:
        AccessControl.require_permissions(user, frozenset({LIST_BOOKMARKS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return bookmark_repository.list_bookmarked_artifacts(chat_id, user.id)


bookmark_service = BookmarkService()
