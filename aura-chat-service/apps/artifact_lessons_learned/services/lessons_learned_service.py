import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact_lessons_learned.exceptions import (
    LessonsLearnedAccessDeniedException,
    LessonsLearnedNotFoundException,
    LLMServiceException,
)
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem
from apps.artifact_lessons_learned.repositories.lessons_learned_repository import lessons_learned_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Extraé las lecciones aprendidas a partir del o los documentos adjuntos."


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
        query: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        description: str,
        items: list,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.LESSONS_LEARNED,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    ll = lessons_learned_repository.create(
        user_id=user_id,
        items=items,
        artifact_id=artifact.id,
        title=title,
        query=query,
        description=description,
    )
    return artifact, ll


class LessonsLearnedService(ArtifactCrudService):
    repository = lessons_learned_repository
    not_found_exc = LessonsLearnedNotFoundException
    access_denied_exc = LessonsLearnedAccessDeniedException
    log_model = "ArtifactLessonsLearned"
    log_id_key = "lessons_learned_id"
    perm_list = perms.LIST_LESSONS_LEARNED
    perm_manage = perms.MANAGE_LESSONS_LEARNED
    perm_get = perms.GET_LESSONS_LEARNED
    perm_export = perms.EXPORT_LESSONS_LEARNED
    perm_manage_export = perms.MANAGE_EXPORT_LESSONS_LEARNED
    perm_delete = perms.DELETE_LESSONS_LEARNED
    logger = logger

    def list_lessons_learned(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_lessons_learned(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> ArtifactLessonsLearned:
        return self._get(user, lessons_learned_id)

    def get_own_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> ArtifactLessonsLearned:
        return self._get_own(user, lessons_learned_id)

    def get_lessons_learned_admin_export(self, user: AuthenticatedUser,
                                         lessons_learned_id: int) -> ArtifactLessonsLearned:
        return self._get_admin_export(user, lessons_learned_id)

    def delete_lessons_learned(self, user: AuthenticatedUser, lessons_learned_id: int) -> None:
        self._delete(user, lessons_learned_id)

    async def generate_lessons_learned(
            self,
            user: AuthenticatedUser,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactLessonsLearned, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_LESSONS_LEARNED_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)

        human_text = message.strip() if message else _DOCUMENTS_ONLY_INSTRUCTION
        messages = history + [{"role": "human", "content": human_text}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_lessons_learned_stream_events(
                    messages=messages,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
                    document_ids=document_ids,
            ):
                et = event.get("type")
                if et == "progress":
                    await broadcast_artifact_progress(chat_id, str(event.get("step", "")),
                                                      str(event.get("message", "")))
                elif et == "complete":
                    result_data = event.get("result") or {}
                elif et == "error":
                    logger.error(
                        "LLM lessons-learned stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM lessons-learned-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM lessons-learned stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        title = str(result_data.get("title", "")).strip()
        raw_items = result_data.get("items") or []
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))
        description = str(result_data.get("description", ""))

        if not title:
            logger.error("LLM returned empty title for lessons-learned", extra={"user_id": user.id})
            raise LLMServiceException()
        if not raw_items:
            logger.error("LLM returned empty items for lessons-learned", extra={"user_id": user.id})
            raise LLMServiceException()

        items = _normalize_items(raw_items)
        artifact, ll = await sync_to_async(_persist_generated_lessons_learned)(
            user_id=user.id,
            title=title,
            query=message,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            description=description,
            items=items,
            fragments=fragments,
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
        return ll, out_messages, fragments


lessons_learned_service = LessonsLearnedService()
