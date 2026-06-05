import logging
from typing import Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ReportGenerateResult, llm_client
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact.services.artifact_access import assert_detail_access
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created
from apps.artifact.services.artifact_service import create_artifact_for_content, _cleanup_artifact_interactions
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


def _assert_report_access(user_id: int, report, *, require_contributor: bool = False) -> None:
    assert_detail_access(user_id, report, ReportAccessDeniedException(), require_contributor=require_contributor)


@transaction.atomic
def _persist_generated_report(
        *,
        user_id: int,
        report_type: str,
        title: str,
        mode: str,
        source_chat_id: int,
        content: str,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.REPORT,
        title=title,
        mode=mode,
        source_chat_id=source_chat_id,
    )
    report = report_repository.create(
        user_id=user_id,
        type=report_type,
        content=content,
        artifact_id=artifact.id,
    )
    return artifact, report


class ReportService:
    def list_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
            chat_id: Optional[int] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_REPORTS}))
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return report_repository.list_by_chat(source_chat_id=chat_id, report_type=report_type)
        return report_repository.list_by_user(user_id=user.id, report_type=report_type)

    def list_all_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_REPORTS}))
        return report_repository.list_all(report_type=report_type)

    def get_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        AccessControl.require_permissions(user, frozenset({perms.GET_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report)
        return report

    def get_own_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        AccessControl.require_permissions(user, frozenset({perms.EXPORT_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report)
        return report

    def get_report_admin_export(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_EXPORT_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        return report

    @transaction.atomic
    def update_report(
            self,
            user: AuthenticatedUser,
            report_id: int,
            title: Optional[str] = None,
            content: Optional[str] = None,
    ) -> ArtifactReport:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report, require_contributor=True)
        if title is not None:
            artifact_repository.update(
                report.artifact,
                updated_by=user.id,
                title=title,
            )
        return report_repository.update(report, updated_by=user.id, content=content)

    @transaction.atomic
    def delete_report(self, user: AuthenticatedUser, report_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_REPORT}))
        report = report_repository.get_by_id(report_id)
        if report is None:
            raise ReportNotFoundException()
        _assert_report_access(user.id, report, require_contributor=True)
        report_repository.soft_delete(report, deleted_by=user.id)
        _cleanup_artifact_interactions(report.artifact_id)
        artifact_repository.soft_delete(report.artifact, deleted_by=user.id)
        logger.info("ArtifactReport deleted", extra={"user_id": user.id, "report_id": report_id})

    async def generate_report(
            self,
            user: AuthenticatedUser,
            report_type: str,
            message: str,
            mode: str,
            chat_id: int,
    ) -> tuple[ArtifactReport, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_REPORT_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        is_contributor = await sync_to_async(membership_repository.is_active_contributor)(chat_id, user.id)
        if not is_contributor:
            raise ChatAccessDeniedException()
        history = await sync_to_async(build_chat_history)(chat_id)

        messages = history + [{"role": "human", "content": message}]
        try:
            result: ReportGenerateResult = await llm_client.generate_report(
                messages=messages,
                mode=mode,
                report_type=report_type,
                user=user,
                chat_id=chat_id,
            )
        except HttpClientException as e:
            logger.error(
                "LLM report-generate failed: %s",
                str(e),
                extra={"user_id": user.id, "report_type": report_type, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if not result.content or not result.content.strip():
            logger.error("LLM returned empty content for report",
                         extra={"user_id": user.id, "report_type": report_type})
            raise LLMServiceException()
        if result.report_type not in ArtifactReport.Type.values:
            logger.error("LLM returned unknown report type: %s", result.report_type, extra={"user_id": user.id})
            raise LLMServiceException()

        title = _auto_title(result.report_type, result.content)
        artifact, report = await sync_to_async(_persist_generated_report)(
            user_id=user.id,
            report_type=result.report_type,
            title=title,
            mode=mode,
            source_chat_id=chat_id,
            content=result.content,
        )
        logger.info(
            "ArtifactReport generated and saved",
            extra={
                "user_id": user.id,
                "report_id": report.id,
                "type": result.report_type,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return report, result.messages, result.fragments


report_service = ReportService()
