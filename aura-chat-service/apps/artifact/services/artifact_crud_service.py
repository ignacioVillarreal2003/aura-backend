import logging

from django.db import transaction

from core.authorization.access import AccessControl
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact.services.artifact_access import assert_detail_access
from apps.artifact.services.artifact_service import _cleanup_artifact_interactions

base_logger = logging.getLogger(__name__)


class ArtifactCrudService:
    """Shared list/get/delete + permission flow for artifact sub-services.

    Subclasses declare the per-artifact configuration below and expose their
    own public methods (e.g. ``get_report``) that delegate to the generic
    ``_get`` / ``_delete`` helpers, keeping the existing call signatures intact.
    """

    # --- per-artifact configuration (override in subclasses) ---
    repository = None
    not_found_exc: type = None
    access_denied_exc: type = None
    log_model: str = ""
    log_id_key: str = ""
    perm_list = None
    perm_manage = None
    perm_get = None
    perm_export = None
    perm_manage_export = None
    perm_delete = None
    logger = base_logger

    def _assert_access(self, user_id, obj, *, require_contributor: bool = False) -> None:
        assert_detail_access(user_id, obj, self.access_denied_exc(), require_contributor=require_contributor)

    def _get_or_404(self, obj_id):
        obj = self.repository.get_by_id(obj_id)
        if obj is None:
            raise self.not_found_exc()
        return obj

    def _list_by_chat(self, user, chat_id, **filters):
        AccessControl.require_permissions(user, frozenset({self.perm_list}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return self.repository.list_by_chat(source_chat_id=chat_id, **filters)

    def _list_all(self, user, **filters):
        AccessControl.require_permissions(user, frozenset({self.perm_manage}))
        return self.repository.list_all(**filters)

    def _get(self, user, obj_id):
        AccessControl.require_permissions(user, frozenset({self.perm_get}))
        obj = self._get_or_404(obj_id)
        self._assert_access(user.id, obj)
        return obj

    def _get_own(self, user, obj_id):
        AccessControl.require_permissions(user, frozenset({self.perm_export}))
        obj = self._get_or_404(obj_id)
        self._assert_access(user.id, obj)
        return obj

    def _get_admin_export(self, user, obj_id):
        AccessControl.require_permissions(user, frozenset({self.perm_manage_export}))
        return self._get_or_404(obj_id)

    @transaction.atomic
    def _delete(self, user, obj_id) -> None:
        AccessControl.require_permissions(user, frozenset({self.perm_delete}))
        obj = self.repository.get_by_id_for_update(obj_id)
        if obj is None:
            raise self.not_found_exc()
        self._assert_access(user.id, obj, require_contributor=True)
        self.repository.soft_delete(obj, deleted_by=user.id)
        _cleanup_artifact_interactions(obj.artifact_id)
        artifact_repository.soft_delete(obj.artifact, deleted_by=user.id)
        self.logger.info("%s deleted", self.log_model, extra={"user_id": user.id, self.log_id_key: obj_id})
