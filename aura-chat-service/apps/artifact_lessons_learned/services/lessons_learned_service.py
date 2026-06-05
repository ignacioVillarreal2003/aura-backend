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
from apps.artifact_lessons_learned.exceptions import (
    LessonsLearnedAccessDeniedException,
    LessonsLearnedNotFoundException,
    LLMServiceException,
)
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem
from apps.artifact_lessons_learned.repositories.lessons_learned_repository import lessons_learned_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)


def _assert_access(user_id: int, ll, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, ll, LessonsLearnedAccessDeniedException(), require_contributor=require_contributor)


def _normalize_items(items: list) -> list:
    valid_categories = {c.value for c in ArtifactLessonsLearnedItem.Category}
    normalized = []
    for idx, item in enumerate(items):
        category = str(item.get("category", ArtifactLessonsLearnedItem.Category.SUSTAIN))
        if category not in valid_categories:
            category = ArtifactLessonsLearnedItem.Category.SUSTAIN
        normalized.append({
            "category": category,
            "observation": str(item.get("observation", "")),
            "discussion": str(item.get("discussion", "")),
            "recommendation": str(item.get("recommendation", "")),
            "position": idx,
        })
    return normalized


@transaction.atomic
def _persist_generated_lessons_learned(
        *,
        user_id: int,
        title: str,
        mode: str,
        source_chat_id: int,
        context: str,
        items: list,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.LESSONS_LEARNED,
        title=title,
        mode=mode,
        source_chat_id=source_chat_id,
    )
    ll = lessons_learned_repository.create(
        user_id=user_id,
        context=context,
        items=items,
        artifact_id=artifact.id,
    )
    return artifact, ll


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

    def get_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> ArtifactLessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.GET_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll)
        return ll

    def get_own_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> ArtifactLessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll)
        return ll

    def get_lessons_learned_admin_export(self, user: AuthenticatedUser, lessons_learned_id: int) -> ArtifactLessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        return ll

    @transaction.atomic
    def update_lessons_learned(
            self,
            user: AuthenticatedUser,
            lessons_learned_id: int,
            title: Optional[str] = None,
            context: Optional[str] = None,
            items: Optional[list] = None,
    ) -> ArtifactLessonsLearned:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll, require_contributor=True)
        if title is not None:
            artifact_repository.update(ll.artifact, updated_by=user.id, title=title)
        normalized = _normalize_items(items) if items is not None else None
        return lessons_learned_repository.update(
            ll,
            updated_by=user.id,
            context=context,
            items=normalized,
        )

    @transaction.atomic
    def delete_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_LESSONS_LEARNED}))
        ll = lessons_learned_repository.get_by_id(lessons_learned_id)
        if ll is None:
            raise LessonsLearnedNotFoundException()
        _assert_access(user.id, ll, require_contributor=True)
        lessons_learned_repository.soft_delete(ll, deleted_by=user.id)
        _cleanup_artifact_interactions(ll.artifact_id)
        artifact_repository.soft_delete(ll.artifact, deleted_by=user.id)
        logger.info("ArtifactLessonsLearned deleted", extra={"user_id": user.id, "lessons_learned_id": lessons_learned_id})

    async def generate_lessons_learned(
            self,
            user: AuthenticatedUser,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactLessonsLearned, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_LESSONS_LEARNED_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        is_contributor = await sync_to_async(membership_repository.is_active_contributor)(chat_id, user.id)
        if not is_contributor:
            raise ChatAccessDeniedException()
        history = await sync_to_async(build_chat_history)(chat_id)

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
        artifact, ll = await sync_to_async(_persist_generated_lessons_learned)(
            user_id=user.id,
            title=result.title,
            mode=mode,
            source_chat_id=chat_id,
            context=result.context or "",
            items=items,
        )
        logger.info(
            "ArtifactLessonsLearned generated and saved",
            extra={
                "user_id": user.id,
                "lessons_learned_id": ll.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return ll, result.messages, result.fragments


lessons_learned_service = LessonsLearnedService()
