import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ChecklistGenerateResult, llm_client
from apps.checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException, LLMServiceException
from apps.checklist.models import Checklist
from apps.checklist.repositories.checklist_repository import checklist_repository

logger = logging.getLogger(__name__)


class ChecklistService:
    def list_checklists(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.LIST_CHECKLISTS}))
        return checklist_repository.list_by_user(user_id=user.id)

    def list_all_checklists(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_CHECKLISTS}))
        return checklist_repository.list_all()

    def get_checklist(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.GET_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        return checklist

    def get_own_checklist(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        if checklist.created_by != user.id:
            raise ChecklistAccessDeniedException()
        return checklist

    def get_checklist_admin_export(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
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

    async def generate_checklist(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
    ) -> tuple[Checklist, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_CHECKLIST_GENERATE}))
        messages = [{"role": "human", "content": message}]
        try:
            result: ChecklistGenerateResult = await llm_client.generate_checklist(
                messages=messages,
                mode=mode,
                user=user,
            )
        except HttpClientException as e:
            logger.error(
                "LLM checklist-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        checklist = await sync_to_async(checklist_repository.create)(
            user_id=user.id,
            title=result.title,
            items=result.items,
            mode=mode,
            metadata={},
        )
        logger.info(
            "Checklist generated and saved",
            extra={"user_id": user.id, "checklist_id": checklist.id},
        )
        return checklist, result.messages, result.fragments


checklist_service = ChecklistService()
