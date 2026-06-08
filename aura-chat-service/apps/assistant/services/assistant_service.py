import logging
from typing import Optional
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from apps.assistant.exceptions import (
    AssistantAlreadyExistsException,
    AssistantInactiveException,
    AssistantNotFoundException,
)
from apps.assistant.models import Assistant
from apps.assistant.repositories.assistant_repository import assistant_repository
from apps.chat.repositories.chat_repository import chat_repository

logger = logging.getLogger(__name__)


class AssistantService:
    def create_assistant(
            self,
            user: AuthenticatedUser,
            name: str,
            description: str,
            system_prompt: str,
            avatar_emoji: str,
            is_active: bool,
            response_style: str = "",
    ) -> Assistant:
        AccessControl.require_permissions(user, frozenset({perms.CREATE_ASSISTANT}))
        if assistant_repository.exists_with_name(name):
            raise AssistantAlreadyExistsException()
        try:
            with transaction.atomic():
                assistant = assistant_repository.create(
                    user_id=user.id,
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    avatar_emoji=avatar_emoji,
                    is_active=is_active,
                )
        except IntegrityError:
            raise AssistantAlreadyExistsException()
        logger.info("Assistant created", extra={"user_id": user.id, "assistant_id": assistant.id})
        return assistant

    def list_active_assistants(self, user: AuthenticatedUser, search: Optional[str] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_ASSISTANTS}))
        return assistant_repository.list_active(search=search)

    def list_all_assistants(self, user: AuthenticatedUser, search: Optional[str] = None):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_ASSISTANTS}))
        return assistant_repository.list_all(search=search)

    def get_assistant(self, user: AuthenticatedUser, assistant_id: int) -> Assistant:
        AccessControl.require_permissions(user, frozenset({perms.GET_ASSISTANT}))
        assistant = assistant_repository.get_by_id(assistant_id)
        if assistant is None or not assistant.is_active:
            raise AssistantNotFoundException()
        return assistant

    @transaction.atomic
    def update_assistant(
            self,
            user: AuthenticatedUser,
            assistant_id: int,
            name: Optional[str] = None,
            description: Optional[str] = None,
            system_prompt: Optional[str] = None,
            response_style: Optional[str] = None,
            avatar_emoji: Optional[str] = None,
            is_active: Optional[bool] = None,
    ) -> Assistant:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_ASSISTANT}))
        assistant = assistant_repository.get_by_id_for_update(assistant_id)
        if assistant is None:
            raise AssistantNotFoundException()
        if name is not None and name != assistant.name and assistant_repository.exists_with_name(name):
            raise AssistantAlreadyExistsException()
        try:
            return assistant_repository.update(
                assistant,
                name=name,
                description=description,
                system_prompt=system_prompt,
                response_style=response_style,
                avatar_emoji=avatar_emoji,
                is_active=is_active,
                updated_by=user.id,
            )
        except IntegrityError:
            raise AssistantAlreadyExistsException()

    def delete_assistant(self, user: AuthenticatedUser, assistant_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_ASSISTANT}))
        assistant = assistant_repository.get_by_id(assistant_id)
        if assistant is None:
            raise AssistantNotFoundException()
        assistant_repository.soft_delete(assistant, deleted_by=user.id)
        logger.info("Assistant deleted", extra={"user_id": user.id, "assistant_id": assistant_id})

    def start_chat(self, user: AuthenticatedUser, assistant_id: int, resume: bool = False):
        AccessControl.require_permissions(user, frozenset({perms.USE_ASSISTANT}))

        assistant = assistant_repository.get_by_id(assistant_id)
        if assistant is None:
            raise AssistantNotFoundException()
        if not assistant.is_active:
            raise AssistantInactiveException()

        if resume:
            existing = chat_repository.get_latest_by_assistant(user.id, assistant_id)
            if existing is not None:
                logger.info(
                    "Assistant chat resumed",
                    extra={"user_id": user.id, "assistant_id": assistant_id, "chat_id": existing.id},
                )
                return existing, False

        return self._create_assistant_chat(user, assistant), True

    @staticmethod
    def _create_assistant_chat(user: AuthenticatedUser, assistant: Assistant):
        from apps.chat.services.chat_service import chat_service

        ts = timezone.now().strftime("%d/%m/%Y %H:%M")
        chat_name = f"{assistant.name} — {ts}"

        chat = chat_service.create_chat(
            user=user,
            name=chat_name,
            system_prompt=assistant.system_prompt,
            response_style=assistant.response_style,
            source_assistant_id=assistant.id,
        )

        logger.info(
            "Assistant chat started",
            extra={"user_id": user.id, "assistant_id": assistant.id, "chat_id": chat.id},
        )
        return chat


assistant_service = AssistantService()
