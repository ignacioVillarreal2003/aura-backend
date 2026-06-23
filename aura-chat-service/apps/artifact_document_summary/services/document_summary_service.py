import logging
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from apps.artifact_document_summary.exceptions import (
    DocumentSummaryAccessDeniedException,
    DocumentSummaryNotFoundException,
    LLMServiceException,
)
from apps.artifact_document_summary.models import ArtifactDocumentSummary
from apps.artifact_document_summary.repositories.document_summary_repository import document_summary_repository
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService

logger = logging.getLogger(__name__)

@transaction.atomic
def _persist_generated_document_summary(
        *,
        user_id: int,
        title: str,
        description: str,
        source_chat_id: int,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list,
        summary: str,
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.DOCUMENT_SUMMARY,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    obj = document_summary_repository.create(
        user_id=user_id,
        summary=summary,
        artifact_id=artifact.id,
        title=title,
        description=description,
    )
    return artifact, obj


class DocumentSummaryService(ArtifactCrudService):
    repository = document_summary_repository
    not_found_exc = DocumentSummaryNotFoundException
    access_denied_exc = DocumentSummaryAccessDeniedException
    log_model = "ArtifactDocumentSummary"
    log_id_key = "document_summary_id"
    perm_list = perms.LIST_DOCUMENT_SUMMARIES
    perm_manage = perms.MANAGE_DOCUMENT_SUMMARIES
    perm_get = perms.GET_DOCUMENT_SUMMARY
    perm_export = perms.EXPORT_DOCUMENT_SUMMARY
    perm_manage_export = perms.MANAGE_EXPORT_DOCUMENT_SUMMARY
    perm_delete = perms.DELETE_DOCUMENT_SUMMARY
    logger = logger

    def list_document_summaries(self, user: AuthenticatedUser, chat_id: int):
        return self._list_by_chat(user, chat_id)

    def list_all_document_summaries(self, user: AuthenticatedUser):
        return self._list_all(user)

    def get_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> ArtifactDocumentSummary:
        return self._get(user, document_summary_id)

    def get_own_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> ArtifactDocumentSummary:
        return self._get_own(user, document_summary_id)

    def get_document_summary_admin_export(
            self, user: AuthenticatedUser, document_summary_id: int
    ) -> ArtifactDocumentSummary:
        return self._get_admin_export(user, document_summary_id)

    def delete_document_summary(self, user: AuthenticatedUser, document_summary_id: int) -> None:
        self._delete(user, document_summary_id)

    async def generate_document_summary(
            self,
            user: AuthenticatedUser,
            document_ids: list,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> tuple[ArtifactDocumentSummary, list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_DOCUMENT_SUMMARY_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None

        result_data: dict | None = None
        try:
            async for event in llm_client.execute_document_summary_stream_events(
                    document_ids=document_ids,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
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

        title = str(result_data.get("title", "")).strip() or "Resumen de documentos"
        description = str(result_data.get("description", "")).strip()
        artifact, obj = await sync_to_async(_persist_generated_document_summary)(
            user_id=user.id,
            title=title,
            description=description,
            source_chat_id=chat_id,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
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
