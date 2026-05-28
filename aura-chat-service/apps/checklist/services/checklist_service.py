import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ChecklistGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException, LLMServiceException
from apps.checklist.models import Checklist
from apps.checklist.repositories.checklist_repository import checklist_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)


def _assert_checklist_access(user_id: int, checklist: Checklist, *, require_owner: bool = False) -> None:
    if checklist.created_by == user_id:
        return
    if checklist.source_chat_id is not None:
        if require_owner:
            if membership_repository.is_chat_owner(checklist.source_chat_id, user_id):
                return
        else:
            if membership_repository.is_active_member(checklist.source_chat_id, user_id):
                return
    raise ChecklistAccessDeniedException()


class ChecklistService:
    def list_checklists(self, user: AuthenticatedUser, chat_id: Optional[int] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_CHECKLISTS}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
        return checklist_repository.list_by_user(user_id=user.id, source_chat_id=chat_id)

    def list_all_checklists(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_CHECKLISTS}))
        return checklist_repository.list_all()

    def get_checklist(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.GET_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist)
        return checklist

    def get_own_checklist(self, user: AuthenticatedUser, checklist_id: int) -> Checklist:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist)
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
        _assert_checklist_access(user.id, checklist)
        return checklist_repository.update(checklist, updated_by=user.id, title=title, items=items)

    def delete_checklist(self, user: AuthenticatedUser, checklist_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_CHECKLIST}))
        checklist = checklist_repository.get_by_id(checklist_id)
        if checklist is None:
            raise ChecklistNotFoundException()
        _assert_checklist_access(user.id, checklist, require_owner=True)
        checklist_repository.soft_delete(checklist, deleted_by=user.id)
        logger.info("Checklist deleted", extra={"user_id": user.id, "checklist_id": checklist_id})

    async def generate_checklist(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: Optional[int] = None,
    ) -> tuple[Checklist, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_CHECKLIST_GENERATE}))

        history: list[dict] = []
        if chat_id is not None:
            chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
            if chat is None:
                raise ChatNotFoundException()
            is_member = await sync_to_async(membership_repository.is_active_member)(chat_id, user.id)
            if not is_member:
                raise ChatAccessDeniedException()
            recent = await sync_to_async(message_repository.get_recent_messages)(chat_id, limit=20)
            recent.reverse()
            for msg in recent:
                role = "human" if msg.sender_type == ChatMessage.SenderType.USER else "assistant"
                history.append({"role": role, "content": msg.message})

        messages = history + [{"role": "human", "content": message}]
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

        if not result.title or not result.title.strip():
            logger.error("LLM returned empty title for checklist", extra={"user_id": user.id})
            raise LLMServiceException()
        if not result.items:
            logger.error("LLM returned empty items for checklist", extra={"user_id": user.id})
            raise LLMServiceException()

        checklist = await sync_to_async(checklist_repository.create)(
            user_id=user.id,
            title=result.title,
            items=result.items,
            mode=mode,
            metadata={},
            source_chat_id=chat_id,
        )
        logger.info(
            "Checklist generated and saved",
            extra={"user_id": user.id, "checklist_id": checklist.id, "source_chat_id": chat_id},
        )
        return checklist, result.messages, result.fragments


checklist_service = ChecklistService()
