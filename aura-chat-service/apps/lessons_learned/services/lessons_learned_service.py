import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import LessonsLearnedGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.lessons_learned.exceptions import (
    LessonsLearnedAccessDeniedException,
    LessonsLearnedNotFoundException,
    LLMServiceException,
)
from apps.lessons_learned.models import LessonsLearned, LessonsLearnedItem
from apps.lessons_learned.repositories.lessons_learned_repository import lessons_learned_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)


def _assert_access(user_id: int, ll: LessonsLearned, *, require_contributor: bool = False) -> None:
    if ll.created_by == user_id:
        return
    if ll.source_chat_id is not None:
        checker = (
            membership_repository.is_active_contributor
            if require_contributor
            else membership_repository.is_active_member
        )
        if checker(ll.source_chat_id, user_id):
            return
    raise LessonsLearnedAccessDeniedException()


def _normalize_items(items: list) -> list:
    valid_categories = {c.value for c in LessonsLearnedItem.Category}
    normalized = []
    for idx, item in enumerate(items):
        category = str(item.get("category", LessonsLearnedItem.Category.SUSTAIN))
        if category not in valid_categories:
            category = LessonsLearnedItem.Category.SUSTAIN
        normalized.append({
            "category": category,
            "observation": str(item.get("observation", "")),
            "discussion": str(item.get("discussion", "")),
            "recommendation": str(item.get("recommendation", "")),
            "position": idx,
        })
    return normalized


class LessonsLearnedService:
    def list_lessons_learned(self, user: AuthenticatedUser, chat_id: Optional[int] = None):
        AccessControl.require_permissions(user, frozenset({perms.LIST_LESSONS_LEARNED}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return lessons_learned_repository.list_by_chat(source_chat_id=chat_id)
        return lessons_learned_repository.list_by_user(user_id=user.id)

    def list_all_lessons_learned(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_LESSONS_LEARNED}))
        return lessons_learned_repository.list_all()

    def get_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> LessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.GET_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll)
        return ll

    def get_own_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> LessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll)
        return ll

    def get_lessons_learned_admin_export(self, user: AuthenticatedUser, lessons_learned_id: int) -> LessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        return ll

    def update_lessons_learned(
            self,
            user: AuthenticatedUser,
            lessons_learned_id: int,
            title: Optional[str] = None,
            context: Optional[str] = None,
            what_went_well: Optional[str] = None,
            what_failed: Optional[str] = None,
            recommendations: Optional[str] = None,
            items: Optional[list] = None,
    ) -> LessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll, require_contributor=True)
        normalized = _normalize_items(items) if items is not None else None
        return lessons_learned_repository.update(
            ll,
            updated_by=user.id,
            title=title,
            context=context,
            what_went_well=what_went_well,
            what_failed=what_failed,
            recommendations=recommendations,
            items=normalized,
        )

    def delete_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll, require_contributor=True)
        lessons_learned_repository.soft_delete(ll, deleted_by=user.id)
        logger.info("LessonsLearned deleted", extra={"user_id": user.id, "lessons_learned_id": lessons_learned_id})

    async def generate_lessons_learned(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: Optional[int] = None,
    ) -> tuple[LessonsLearned, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_LESSONS_LEARNED_GENERATE}))

        history: list[dict] = []
        if chat_id is not None:
            chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
            if chat is None:
                raise ChatNotFoundException()
            is_contributor = await sync_to_async(membership_repository.is_active_contributor)(chat_id, user.id)
            if not is_contributor:
                raise ChatAccessDeniedException()
            recent = await sync_to_async(message_repository.get_recent_messages)(chat_id, limit=20)
            recent.reverse()
            for msg in recent:
                role = "human" if msg.sender_type == ChatMessage.SenderType.USER else "assistant"
                history.append({"role": role, "content": msg.message})

        messages = history + [{"role": "human", "content": message}]
        try:
            result: LessonsLearnedGenerateResult = await llm_client.generate_lessons_learned(
                messages=messages,
                mode=mode,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM lessons-learned-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.title or not result.title.strip():
            logger.error("LLM returned empty title for lessons-learned", extra={"user_id": user.id})
            raise LLMServiceException()
        if not result.items:
            logger.error("LLM returned empty items for lessons-learned", extra={"user_id": user.id})
            raise LLMServiceException()

        items = _normalize_items(result.items)
        artifact_id = await sync_to_async(self._create_artifact_header)(
            user_id=user.id,
            title=result.title,
            source_chat_id=chat_id,
        )
        ll = await sync_to_async(lessons_learned_repository.create)(
            user_id=user.id,
            title=result.title,
            context=result.context,
            what_went_well=result.what_went_well,
            what_failed=result.what_failed,
            recommendations=result.recommendations,
            items=items,
            mode=mode,
            source_chat_id=chat_id,
            artifact_id=artifact_id,
        )
        logger.info(
            "LessonsLearned generated and saved",
            extra={
                "user_id": user.id,
                "lessons_learned_id": ll.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact_id,
            },
        )
        return ll, result.messages, result.fragments

    @staticmethod
    def _create_artifact_header(
            *,
            user_id: int,
            title: str,
            source_chat_id: Optional[int],
    ) -> Optional[int]:
        try:
            artifact = artifact_repository.create(
                user_id=user_id,
                type=Artifact.Type.LESSONS_LEARNED,
                title=title,
                status=Artifact.Status.FINAL,
                source_chat_id=source_chat_id,
            )
            return artifact.id
        except Exception:
            logger.warning(
                "Failed to create artifact header for lessons-learned",
                extra={"user_id": user_id, "source_chat_id": source_chat_id},
                exc_info=True,
            )
            return None


lessons_learned_service = LessonsLearnedService()
