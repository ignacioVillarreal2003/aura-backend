import logging
from typing import Optional

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms

from apps.checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException
from apps.checklist.models import Checklist
from apps.checklist.repositories.checklist_repository import checklist_repository

logger = logging.getLogger(__name__)


class ChecklistService:
    def create_checklist(
            self,
            user: AuthenticatedUser,
            title: str,
            items: list,
            mode: str,
            metadata: dict,
    ) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.CREATE_CHECKLIST}))
        checklist = checklist_repository.create(
            user_id=user.id,
            title=title,
            items=items,
            mode=mode,
            metadata=metadata,
        )
        logger.info("Checklist created", extra={"user_id": user.id, "checklist_id": checklist.id})
        return checklist

    def list_checklists(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.LIST_CHECKLISTS}))
        return checklist_repository.list_by_user(user_id=user.id)

    def get_checklist(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.GET_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        if checklist.created_by != user.id:
            raise ChecklistAccessDeniedException()
        return checklist

    def update_checklist(
            self,
            user: AuthenticatedUser,
            checklist_id: int,
            title: Optional[str] = None,
            items: Optional[list] = None,
    ) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        if checklist.created_by != user.id:
            raise ChecklistAccessDeniedException()
        return checklist_repository.update(checklist, title=title, items=items)

    def delete_checklist(self, user: AuthenticatedUser, checklist_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        if checklist.created_by != user.id:
            raise ChecklistAccessDeniedException()
        checklist_repository.soft_delete(checklist, deleted_by=user.id)
        logger.info("Checklist deleted", extra={"user_id": user.id, "checklist_id": checklist_id})


checklist_service = ChecklistService()
