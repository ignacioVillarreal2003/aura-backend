import logging
from typing import Optional
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact_document_summary.exceptions import (
    DocumentSummaryAccessDeniedException,
    DocumentSummaryNotFoundException,
    LLMServiceException,
)
from apps.artifact_document_summary.models import ArtifactDocumentSummary
from apps.artifact_document_summary.repositories.document_summary_repository import document_summary_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions

logger = logging.getLogger(__name__)

_MAX_TITLE_CHARS = 200


def _assert_access(user_id: int, obj, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, obj, DocumentSummaryAccessDeniedException(), require_contributor=require_contributor)


def _derive_title(summary: str) -> str:
    text = summary.strip()
    if not text:
        return "Resumen de documentos"
    truncated = text[:_MAX_TITLE_CHARS]
    if len(text) > _MAX_TITLE_CHARS:
        truncated = truncated.rstrip() + "..."
    return truncated


@transaction.atomic
def _persist_generated_document_summary(
        *,
        user_id: int,
        title: str,
        source_chat_id: int,
        document_ids: list,
        summary: str,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.DOCUMENT_SUMMARY,
        title=title,
        mode=Artifact.Mode.DIRECT,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    obj = document_summary_repository.create(
        user_id=user_id,
        document_ids=document_ids,
        summary=summary,
        artifact_id=artifact.id,
    )
    return artifact, obj


class DocumentSummaryService:
    def list_document_summaries(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_DOCUMENT_SUMMARIES}))
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return document_summary_repository.list_by_chat(source_chat_id=chat_id)

    def list_all_document_summaries(self, user: AuthenticatedUser):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_DOCUMENT_SUMMARIES}))
        return document_summary_repository.list_all()

    def get_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> ArtifactDocumentSummary:
        AccessControl.require_permissions(user, frozenset({perms.GET_DOCUMENT_SUMMARY}))
        obj = document_summary_repository.get_by_id(document_summary_id)
        if obj is None:
            raise DocumentSummaryNotFoundException()
        _assert_access(user.id, obj)
        return obj

    def get_own_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> ArtifactDocumentSummary:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_DOCUMENT_SUMMARY}))
        obj = document_summary_repository.get_by_id(document_summary_id)
        if obj is None:
            raise DocumentSummaryNotFoundException()
        _assert_access(user.id, obj)
        return obj

    def get_document_summary_admin_export(
            self, user: AuthenticatedUser, document_summary_id: int
    ) -> ArtifactDocumentSummary:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_DOCUMENT_SUMMARY}))
        obj = document_summary_repository.get_by_id(document_summary_id)
        if obj is None:
            raise DocumentSummaryNotFoundException()
        return obj

    @transaction.atomic
    def update_document_summary(
            self,
            user: AuthenticatedUser,
            document_summary_id: int,
            title: Optional[str] = None,
            summary: Optional[str] = None,
    ) -> ArtifactDocumentSummary:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_DOCUMENT_SUMMARY}))
        obj = document_summary_repository.get_by_id_for_update(document_summary_id)
        if obj is None:
            raise DocumentSummaryNotFoundException()
        _assert_access(user.id, obj, require_contributor=True)
        if title is not None:
            artifact_repository.update(obj.artifact, updated_by=user.id, title=title)
        return document_summary_repository.update(obj, updated_by=user.id, summary=summary)

    @transaction.atomic
    def delete_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_DOCUMENT_SUMMARY}))
        obj = document_summary_repository.get_by_id_for_update(document_summary_id)
        if obj is None:
            raise DocumentSummaryNotFoundException()
        _assert_access(user.id, obj, require_contributor=True)
        document_summary_repository.soft_delete(obj, deleted_by=user.id)
        _cleanup_artifact_interactions(obj.artifact_id)
        artifact_repository.soft_delete(obj.artifact, deleted_by=user.id)
        logger.info(
            "ArtifactDocumentSummary deleted",
            extra={"user_id": user.id, "document_summary_id": document_summary_id},
        )

    async def generate_document_summary(
            self,
            user: AuthenticatedUser,
            document_ids: list,
            chat_id: int,
    ) -> tuple[ArtifactDocumentSummary, list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_DOCUMENT_SUMMARY_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        result_data: dict | None = None
        try:
            async for event in llm_client.execute_document_summary_stream_events(
                    document_ids=document_ids,
                    user=user,
                    chat_id=chat_id,
            ):
                et = event.get("type")
                if et == "progress":
                    await broadcast_artifact_progress(chat_id, str(event.get("step", "")),
                                                      str(event.get("message", "")))
                elif et == "complete":
                    result_data = event.get("result") or {}
                elif et == "error":
                    logger.error(
                        "LLM document-summary stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM document-summary stream failed: %s",
                str(e),
                extra={"user_id": user.id, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM document-summary stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        summary = str(result_data.get("summary", "")).strip()
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))

        if not summary:
            logger.error("LLM returned empty summary for document-summary", extra={"user_id": user.id})
            raise LLMServiceException()

        title = _derive_title(summary)
        artifact, obj = await sync_to_async(_persist_generated_document_summary)(
            user_id=user.id,
            title=title,
            source_chat_id=chat_id,
            document_ids=document_ids,
            summary=summary,
            fragments=fragments,
        )
        logger.info(
            "ArtifactDocumentSummary generated and saved",
            extra={
                "user_id": user.id,
                "document_summary_id": obj.id,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return obj, fragments


document_summary_service = DocumentSummaryService()
