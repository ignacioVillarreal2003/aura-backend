import logging
from typing import Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history
from apps.artifact_report.exceptions import LLMServiceException, ReportAccessDeniedException, ReportNotFoundException
from apps.artifact_report.models import ArtifactReport
from apps.artifact_report.repositories.report_repository import report_repository

logger = logging.getLogger(__name__)

_AUTO_TITLE_MAX_CHARS = 80


def _auto_title(report_type: str, content: str) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    first_line = first_line.lstrip("#").strip()
    if first_line and len(first_line) <= _AUTO_TITLE_MAX_CHARS:
        return first_line
    ts = timezone.now().strftime("%Y-%m-%d %H:%M")
    return f"{report_type} — {ts}"


@transaction.atomic
def _persist_generated_report(
        *,
        user_id: int,
        report_type: str,
        title: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        content: str,
        query: str = "",
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.REPORT,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    report = report_repository.create(
        user_id=user_id,
        type=report_type,
        content=content,
        artifact_id=artifact.id,
        title=title,
        description="",
        query=query,
    )
    return artifact, report


class ReportService(ArtifactCrudService):
    repository = report_repository
    not_found_exc = ReportNotFoundException
    access_denied_exc = ReportAccessDeniedException
    log_model = "ArtifactReport"
    log_id_key = "report_id"
    perm_list = perms.LIST_REPORTS
    perm_manage = perms.MANAGE_REPORTS
    perm_get = perms.GET_REPORT
    perm_export = perms.EXPORT_REPORT
    perm_manage_export = perms.MANAGE_EXPORT_REPORT
    perm_delete = perms.DELETE_REPORT
    logger = logger

    def list_reports(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            report_type: Optional[str] = None,
    ):
        return self._list_by_chat(user, chat_id, report_type=report_type)

    def list_all_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        return self._list_all(user, report_type=report_type)

    def get_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get(user, report_id)

    def get_own_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get_own(user, report_id)

    def get_report_admin_export(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get_admin_export(user, report_id)

    def delete_report(self, user: AuthenticatedUser, report_id: int) -> None:
        self._delete(user, report_id)

    async def generate_report(
            self,
            user: AuthenticatedUser,
            report_type: str,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactReport, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_REPORT_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)

        messages = history + [{"role": "human", "content": message}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_report_stream_events(
                    messages=messages,
                    report_type=report_type,
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
                        "LLM report stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM report-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "report_type": report_type, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM report stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        content = str(result_data.get("content", "")).strip()
        rtype = str(result_data.get("report_type", report_type))
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))

        if not content:
            logger.error("LLM returned empty content for report", extra={"user_id": user.id, "report_type": rtype})
            raise LLMServiceException()
        if rtype not in ArtifactReport.Type.values:
            logger.error("LLM returned unknown report type: %s", rtype, extra={"user_id": user.id})
            raise LLMServiceException()

        title = _auto_title(rtype, content)
        artifact, report = await sync_to_async(_persist_generated_report)(
            user_id=user.id,
            report_type=rtype,
            title=title,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            content=content,
            query=message,
            fragments=fragments,
        )

        report.artifact = artifact
        logger.info(
            "ArtifactReport generated and saved",
            extra={
                "user_id": user.id,
                "report_id": report.id,
                "type": rtype,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return report, out_messages, fragments


report_service = ReportService()
